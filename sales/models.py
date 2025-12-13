# sales/models.py - COMPLETE FIXED VERSION

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, F
import logging

logger = logging.getLogger(__name__)

class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]
    CUSTOMER_TYPE_CHOICES = [('walk_in', 'Walk-in'), ('saved_customer', 'Saved Customer')]
    MONEY_RECEIPT_CHOICES = [('Yes', 'Yes'), ('No', 'No')]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_created')
    sale_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_made')
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    invoice_no = models.CharField(max_length=20, blank=True, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='walk_in')
    with_money_receipt = models.CharField(max_length=3, choices=MONEY_RECEIPT_CHOICES, default='No')
    remark = models.TextField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, blank=True, null=True, related_name='sales')

    class Meta:
        ordering = ['-sale_date', '-id']
        indexes = [
            models.Index(fields=['company', 'sale_date']),
            models.Index(fields=['customer', 'sale_date']),
            models.Index(fields=['invoice_no']),
        ]

    def save(self, *args, **kwargs):
        """Safe save method with recursion prevention"""
        if getattr(self, '_saving', False):
            return super().save(*args, **kwargs)
        
        self._saving = True
        
        try:
            is_new = self.pk is None
            
            # Auto-assign company
            if not self.company and hasattr(self, 'created_by') and self.created_by:
                if hasattr(self.created_by, 'company') and self.created_by.company:
                    self.company = self.created_by.company
            
            if not self.company:
                raise ValidationError("Sale must be associated with a company.")
            
            # Handle customer
            if self.customer_type == 'walk_in':
                if not self.customer_name:
                    self.customer_name = 'Walk-in Customer'
                self.customer = None
            elif self.customer_type == 'saved_customer' and self.customer:
                if self.customer.company != self.company:
                    raise ValidationError('Customer must belong to the same company.')
            
            # Generate invoice number
            if is_new and not self.invoice_no:
                self.invoice_no = self._generate_invoice_no()
            
            # Validate account
            if self.account and self.account.company != self.company:
                self.account = None
            
            # Save first to get PK
            super().save(*args, **kwargs)
            
            # Calculate totals
            self.calculate_totals()
            
            # Handle payment
            self._handle_payment_processing(is_new)
                
        except Exception as e:
            logger.error(f"Error saving sale: {str(e)}", exc_info=True)
            raise
        finally:
            self._saving = False

    def _generate_invoice_no(self):
        """Generate invoice number"""
        if not self.company:
            return f"SL-{int(timezone.now().timestamp())}"
            
        try:
            last_sale = Sale.objects.filter(
                company=self.company,
                invoice_no__regex=r'^SL-\d+$'
            ).order_by('-invoice_no').first()
            
            if last_sale and last_sale.invoice_no:
                try:
                    last_number = int(last_sale.invoice_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    existing_count = Sale.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                existing_count = Sale.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            return f"SL-{new_number}"
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {str(e)}")
            return f"SL-{int(timezone.now().timestamp())}"

    def calculate_totals(self):
        """Calculate all totals for the sale"""
        try:
            # Calculate gross total from items
            items_total = sum(item.subtotal() for item in self.items.all())
            self.gross_total = self._round_decimal(items_total)
            
            # Calculate net total
            self.net_total = self.gross_total
            
            # Calculate charges
            vat_amount = self._calculate_charge(
                self.overall_vat_amount, 
                self.overall_vat_type, 
                self.net_total
            )
            
            service_amount = self._calculate_charge(
                self.overall_service_charge, 
                self.overall_service_type, 
                self.net_total
            )
            
            delivery_amount = self._calculate_charge(
                self.overall_delivery_charge, 
                self.overall_delivery_type, 
                self.net_total
            )
            
            # Calculate overall discount
            overall_discount_amount = self._calculate_charge(
                self.overall_discount,
                self.overall_discount_type,
                self.net_total
            )
            
            # Calculate grand total
            total_charges = vat_amount + service_amount + delivery_amount
            self.payable_amount = self.net_total + total_charges - overall_discount_amount
            
            if self.payable_amount < Decimal('0.00'):
                self.payable_amount = Decimal('0.00')
            
            self.grand_total = self.payable_amount
            
            # Calculate due and change
            self.due_amount = max(Decimal('0.00'), self.grand_total - self.paid_amount)
            self.change_amount = max(Decimal('0.00'), self.paid_amount - self.grand_total)
            
            # Update payment status
            self._update_payment_status()
            
            # Save updated totals
            update_fields = [
                'gross_total', 'net_total', 'payable_amount', 'grand_total',
                'due_amount', 'change_amount', 'payment_status'
            ]
            super().save(update_fields=update_fields)
            
        except Exception as e:
            logger.error(f"Error calculating totals: {str(e)}", exc_info=True)
            raise

    def _calculate_charge(self, amount, charge_type, base_amount):
        """Calculate charge amount based on type"""
        if not amount or amount <= 0:
            return Decimal('0.00')
        
        if charge_type == 'percent':
            return self._round_decimal(base_amount * (amount / Decimal('100.00')))
        else:
            return self._round_decimal(amount)

    def _round_decimal(self, value):
        """Round decimal to 2 decimal places"""
        try:
            if value is None:
                return Decimal('0.00')
            if isinstance(value, (int, float)):
                value = Decimal(str(value))
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except:
            return Decimal('0.00')

    def _update_payment_status(self):
        """Update payment status based on current amounts"""
        try:
            if self.paid_amount >= self.grand_total:
                self.payment_status = 'paid'
            elif self.paid_amount > Decimal('0.00'):
                self.payment_status = 'partial'
            else:
                self.payment_status = 'pending'
                
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            self.payment_status = 'pending'

    def _handle_payment_processing(self, is_new):
        """Handle payment and transaction creation"""
        if self.paid_amount <= 0:
            return
        
        # Update account balance
        if self.account:
            try:
                self.account.balance += self.paid_amount
                self.account.save(update_fields=['balance'])
                logger.info(f"Account {self.account.name} balance updated: +{self.paid_amount}")
            except Exception as e:
                logger.error(f"Error updating account balance: {e}")
        
        # Create money receipt or transaction
        if self.with_money_receipt == 'Yes':
            self.create_money_receipt()
        else:
            self.create_transaction()

    def create_transaction(self):
        """Create transaction for sale"""
        try:
            from transactions.models import Transaction
            
            existing_transaction = Transaction.objects.filter(
                reference_model='sale',
                reference_id=self.id
            ).first()
            
            if existing_transaction:
                return existing_transaction
            
            if self.paid_amount > 0 and self.account:
                transaction = Transaction(
                    company=self.company,
                    account=self.account,
                    amount=self.paid_amount,
                    transaction_type='credit',
                    reference_model='sale',
                    reference_id=self.id,
                    date=timezone.now(),
                    description=f"Sale {self.invoice_no}",
                    created_by=self.created_by
                )
                
                transaction.save()
                return transaction
                
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
        return None
    
    def create_money_receipt(self):
        """Create money receipt for this sale"""
        if self.paid_amount <= 0:
            return None
        
        try:
            from money_receipts.models import MoneyReceipt
            
            existing_receipt = MoneyReceipt.objects.filter(sale=self).first()
            if existing_receipt:
                if existing_receipt.amount != self.paid_amount:
                    existing_receipt.amount = self.paid_amount
                    existing_receipt.save()
                return existing_receipt
            
            money_receipt = MoneyReceipt(
                company=self.company,
                customer=self.customer if self.customer_type == 'saved_customer' else None,
                sale=self,
                amount=self.paid_amount,
                payment_method=self.payment_method or 'Cash',
                payment_date=timezone.now(),
                remark=f"Auto receipt for {self.invoice_no}",
                seller=self.sale_by,
                account=self.account,
                created_by=self.created_by
            )
            
            money_receipt.save()
            return money_receipt
            
        except Exception as e:
            logger.error(f"Error creating money receipt: {e}")
            return None

    def clean(self):
        """Model validation"""
        super().clean()
        
        if not self.company:
            raise ValidationError({'company': 'Sale must be associated with a company.'})
        
        if self.due_amount < 0:
            raise ValidationError({'due_amount': 'Due amount cannot be negative.'})
        
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError({'customer': 'Saved customer must have a customer record.'})
        
        if self.paid_amount > 0 and not self.payment_method:
            raise ValidationError({'payment_method': 'Payment method is required when payment is made.'})

    def __str__(self):
        return f"{self.invoice_no} - {self.get_customer_display()}"

    def get_customer_display(self):
        """Get customer display name"""
        if self.customer_type == 'walk_in':
            return self.customer_name or "Walk-in Customer"
        elif self.customer:
            return self.customer.name
        return "Unknown Customer"

    def add_payment(self, amount, payment_method=None, account=None):
        """Add additional payment to existing sale"""
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
            
        self.paid_amount += amount
        self.save()
        
        return self.paid_amount

    def get_payment_summary(self):
        """Get payment summary for the sale"""
        return {
            'invoice_no': self.invoice_no,
            'grand_total': float(self.grand_total),
            'paid_amount': float(self.paid_amount),
            'due_amount': float(self.due_amount),
            'change_amount': float(self.change_amount),
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
        }

    def can_add_payment(self):
        """Check if additional payment can be added"""
        return self.due_amount > 0 and self.payment_status in ['pending', 'partial']

    @classmethod
    def get_sales_summary(cls, company, start_date=None, end_date=None):
        """Get sales summary for a company"""
        queryset = cls.objects.filter(company=company)
        
        if start_date:
            queryset = queryset.filter(sale_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(sale_date__lte=end_date)
            
        return queryset.aggregate(
            total_sales=models.Count('id'),
            total_amount=models.Sum('grand_total'),
            total_paid=models.Sum('paid_amount'),
            total_due=models.Sum('due_amount')
        )


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), default='fixed')

    class Meta:
        ordering = ['id']

    def subtotal(self):
        """Calculate item subtotal"""
        try:
            total = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
            
            if self.discount_type == 'percent' and self.discount > 0:
                discount_amount = total * (Decimal(str(self.discount)) / Decimal('100.00'))
            elif self.discount_type == 'fixed' and self.discount > 0:
                discount_amount = min(Decimal(str(self.discount)), total)
            else:
                discount_amount = Decimal('0.00')
            
            final_total = max(Decimal('0.00'), total - discount_amount)
            return final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
        except Exception as e:
            logger.error(f"Error calculating subtotal: {str(e)}")
            return Decimal('0.00')

    def save(self, *args, **kwargs):
        """Save sale item with stock management"""
        is_new = self.pk is None
        old_quantity = 0
        
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
                old_quantity = old_item.quantity
            except SaleItem.DoesNotExist:
                pass
        
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}, Requested: {self.quantity}"
                )
        
        super().save(*args, **kwargs)
        
        try:
            if is_new:
                self.product.stock_qty -= self.quantity
            else:
                quantity_change = self.quantity - old_quantity
                self.product.stock_qty -= quantity_change
            
            self.product.save(update_fields=['stock_qty'])
        except Exception as e:
            logger.error(f"Error updating product stock: {e}")
        
        try:
            self.sale.calculate_totals()
        except Exception as e:
            logger.error(f"Error updating sale totals: {e}")

    def delete(self, *args, **kwargs):
        """Delete sale item and restore stock"""
        try:
            self.product.stock_qty += self.quantity
            self.product.save(update_fields=['stock_qty'])
        except Exception as e:
            logger.error(f"Error restoring product stock: {e}")
        
        sale = self.sale
        super().delete(*args, **kwargs)
        
        try:
            sale.calculate_totals()
        except Exception as e:
            logger.error(f"Error updating sale totals after deletion: {e}")

    def __str__(self):
        return f"{self.product.name} x {self.quantity} - {self.subtotal()}"

    def get_item_summary(self):
        """Get item summary"""
        return {
            'product': self.product.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'discount': float(self.discount),
            'discount_type': self.discount_type,
            'subtotal': float(self.subtotal())
        }