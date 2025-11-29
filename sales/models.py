# sales/models.py - COMPLETELY FIXED VERSION

from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Account
from products.models import Product
from core.models import Company
from customers.models import Customer
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
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
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
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
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='sales')

    class Meta:
        ordering = ['-sale_date', '-id']
        indexes = [
            models.Index(fields=['company', 'sale_date']),
            models.Index(fields=['customer', 'sale_date']),
            models.Index(fields=['invoice_no']),
        ]

    def save(self, *args, **kwargs):
        """Safe save method with recursion prevention - FIXED VERSION"""
        
        # Prevent recursion
        if getattr(self, '_saving', False):
            return super().save(*args, **kwargs)
        
        self._saving = True
        
        try:
            is_new = self.pk is None
            old_paid_amount = 0
            
            if not is_new:
                try:
                    old_instance = Sale.objects.get(pk=self.pk)
                    old_paid_amount = old_instance.paid_amount
                except Sale.DoesNotExist:
                    pass
            
            # ✅ FIXED: Auto-assign company from created_by user if not set
            if not self.company and hasattr(self, 'created_by') and self.created_by:
                if hasattr(self.created_by, 'company') and self.created_by.company:
                    self.company = self.created_by.company
                    logger.info(f"Auto-assigned company from user: {self.company}")
            
            # ✅ FIXED: CRITICAL - Ensure company is set before any operations
            if not self.company:
                logger.error("Sale cannot be saved without a company")
                raise ValidationError("Sale must be associated with a company.")
            
            # ✅ FIXED: Validate customer belongs to same company
            if self.customer and self.customer.company != self.company:
                logger.warning(f"Customer company mismatch. Customer: {self.customer.company}, Sale: {self.company}")
                # Reset customer if company doesn't match
                self.customer = None
                self.customer_type = 'walk_in'
                self.customer_name = 'Walk-in Customer'
            
            # Handle customer
            if self.customer_type == 'walk_in' and not self.customer_name:
                self.customer_name = 'Walk-in Customer'
            
            if self.customer_type == 'walk_in' and not self.customer:
                if not self.customer_name or self.customer_name == 'Walk-in Customer':
                    self.customer_name = 'Walk-in Customer'
            
            # ✅ FIXED: Validate saved customer belongs to same company
            if self.customer_type == 'saved_customer' and self.customer:
                if self.customer.company != self.company:
                    raise ValidationError({
                        'customer': 'Customer must belong to the same company.'
                    })
            
            if self.customer_type == 'saved_customer' and not self.customer:
                raise ValidationError({
                    'customer': 'Saved customer must have a customer record.'
                })
            
            # Generate invoice number
            if is_new and not self.invoice_no:
                self.invoice_no = self._generate_invoice_no_safe()
            
            # Set default account if payment is made but no account
            if self.paid_amount > 0 and not self.account:
                self._set_default_account()
            
            # ✅ FIXED: Validate account belongs to same company
            if self.account and self.account.company != self.company:
                logger.warning(f"Account company mismatch. Resetting account.")
                self.account = None
            
            # Save first to get PK
            super().save(*args, **kwargs)
            
            # Update totals after saving
            self.update_totals()
            
            # ✅ FIXED: Create transaction ONLY if no money receipt will be created
            payment_increased = not is_new and self.paid_amount > old_paid_amount
            
            if (is_new or payment_increased) and self.paid_amount > 0:
                if self.with_money_receipt == 'No':
                    # Create sale transaction directly
                    self.create_transaction()
                elif self.with_money_receipt == 'Yes' and not getattr(self, '_skip_money_receipt', False):
                    # Create money receipt (which will create transaction)
                    self.create_money_receipt()
                
        except Exception as e:
            logger.error(f"Error saving sale: {str(e)}")
            raise
        finally:
            self._saving = False

    def _generate_invoice_no_safe(self):
        """Generate invoice number with decimal corruption protection - FIXED VERSION"""
        if not self.company:
            logger.error("Cannot generate invoice number: No company assigned")
            return f"SL-{int(timezone.now().timestamp())}"
            
        try:
            # ✅ FIXED: Get last sale by invoice_no, not by id
            last_sale = Sale.objects.filter(
                company=self.company,
                invoice_no__isnull=False,
                invoice_no__startswith='SL-'
            ).order_by('-invoice_no').first()
            
            if last_sale and last_sale.invoice_no:
                try:
                    # Extract number from "SL-1001" format
                    last_number = int(last_sale.invoice_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing sales for this company
                    existing_count = Sale.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First sale for this company
                existing_count = Sale.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            return f"SL-{new_number}"
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {str(e)}")
            # Fallback: use timestamp
            timestamp = int(timezone.now().timestamp())
            return f"SL-{timestamp}"

    def _set_default_account(self):
        """Set default account for sale"""
        try:
            from accounts.models import Account
            default_account = Account.objects.filter(
                company=self.company, 
                is_active=True
            ).first()
            
            if default_account:
                self.account = default_account
                logger.info(f"Set default account {default_account.name} for {self.invoice_no}")
                
        except Exception as e:
            logger.warning(f"Could not set default account: {e}")

    def create_transaction(self):
        """Create transaction for sale - FIXED VERSION"""
        try:
            from transactions.models import Transaction
            
            # Check if transaction already exists
            existing_transaction = Transaction.objects.filter(
                reference_model='sale',
                reference_id=self.id
            ).first()
            
            if existing_transaction:
                logger.info(f"Transaction already exists for sale {self.invoice_no}")
                return existing_transaction
            
            # Only create transaction if payment was made and account exists
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
                logger.info(f"Sale transaction created: {transaction.transaction_no} for {self.invoice_no}")
                return transaction
                
        except Exception as e:
            logger.error(f"Error creating sale transaction for {self.invoice_no}: {e}")
        return None
    def update_totals(self):
        """Update all calculated totals for the sale - FIXED PAYMENT LOGIC"""
        try:
            if getattr(self, '_updating_totals', False):
                return
                
            self._updating_totals = True
            
            # Calculate from items
            items = self.items.all()
            gross = Decimal('0.00')
            for item in items:
                try:
                    gross += Decimal(str(item.subtotal()))
                except:
                    gross += Decimal('0.00')

            # Calculate discounts and charges safely
            discount_amount = Decimal('0.00')
            try:
                if self.overall_discount_type == 'percent' and self.overall_discount:
                    discount_amount = gross * (Decimal(str(self.overall_discount)) / Decimal('100.00'))
                elif self.overall_discount_type == 'fixed' and self.overall_discount:
                    discount_amount = Decimal(str(self.overall_discount))
            except:
                discount_amount = Decimal('0.00')

            vat_amount = Decimal('0.00')
            try:
                if self.overall_vat_type == 'percent' and self.overall_vat_amount:
                    vat_amount = gross * (Decimal(str(self.overall_vat_amount)) / Decimal('100.00'))
                elif self.overall_vat_type == 'fixed' and self.overall_vat_amount:
                    vat_amount = Decimal(str(self.overall_vat_amount))
            except:
                vat_amount = Decimal('0.00')

            service_amount = Decimal('0.00')
            try:
                if self.overall_service_type == 'percent' and self.overall_service_charge:
                    service_amount = gross * (Decimal(str(self.overall_service_charge)) / Decimal('100.00'))
                elif self.overall_service_type == 'fixed' and self.overall_service_charge:
                    service_amount = Decimal(str(self.overall_service_charge))
            except:
                service_amount = Decimal('0.00')

            delivery_amount = Decimal('0.00')
            try:
                if self.overall_delivery_type == 'percent' and self.overall_delivery_charge:
                    delivery_amount = gross * (Decimal(str(self.overall_delivery_charge)) / Decimal('100.00'))
                elif self.overall_delivery_type == 'fixed' and self.overall_delivery_charge:
                    delivery_amount = Decimal(str(self.overall_delivery_charge))
            except:
                delivery_amount = Decimal('0.00')

            # Calculate totals with safety limits
            max_amount = Decimal('9999999.99')
            
            net_total = gross - discount_amount + vat_amount + service_amount
            grand_total = net_total + delivery_amount

            # Set amounts safely
            self.gross_total = min(self._safe_decimal(gross), max_amount)
            self.net_total = min(self._safe_decimal(net_total), max_amount)
            self.grand_total = min(self._safe_decimal(grand_total), max_amount)
            self.payable_amount = min(self._safe_decimal(grand_total), max_amount)
            
            # ✅ FIXED: Use the actual paid_amount from the model
            paid = self._safe_decimal(self.paid_amount)  # This now uses the saved paid_amount
            payable = self._safe_decimal(self.payable_amount)
            
            # Calculate due amount and change
            if paid > payable:
                # Overpayment - customer paid more than required
                self.due_amount = Decimal('0.00')
                self.change_amount = paid - payable
            else:
                # Normal payment or partial payment
                self.due_amount = payable - paid
                self.change_amount = Decimal('0.00')
            
            # Update payment status
            self._update_payment_status()

            # Save totals
            update_fields = [
                "gross_total", "net_total", "grand_total", 
                "payable_amount", "due_amount", "change_amount",
                "payment_status"
            ]
            
            # Use update to avoid recursion
            Sale.objects.filter(pk=self.pk).update(
                gross_total=self.gross_total,
                net_total=self.net_total,
                grand_total=self.grand_total,
                payable_amount=self.payable_amount,
                due_amount=self.due_amount,
                change_amount=self.change_amount,
                payment_status=self.payment_status
            )
            
        except Exception as e:
            logger.error(f"Error updating totals for {self.invoice_no}: {str(e)}")
        finally:
            self._updating_totals = False



    def _safe_decimal(self, value):
        """Convert value to Decimal safely"""
        try:
            if value is None:
                return Decimal('0.00')
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except:
            return Decimal('0.00')

    def _update_payment_status(self):
        """Update payment status based on current amounts - FIXED SINGLE VERSION"""
        try:
            paid = self._safe_decimal(self.paid_amount)
            payable = self._safe_decimal(self.payable_amount)
            
            if paid >= payable:
                self.payment_status = 'paid'
            elif paid > Decimal('0.00'):
                self.payment_status = 'partial'
            else:
                self.payment_status = 'pending'
                
            logger.info(f"Payment Status Update - Paid: {paid}, Payable: {payable}, Status: {self.payment_status}")
            
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
            self.payment_status = 'pending'

    def create_money_receipt(self):
        """Create money receipt for this sale - FIXED VERSION"""
        if self.paid_amount <= 0:
            return None
        
        try:
            from money_receipts.models import MoneyReceipt
            
            # ✅ FIXED: For walk-in customers, don't set customer in money receipt
            money_receipt_customer = self.customer
            if self.customer_type == 'walk_in':
                money_receipt_customer = None
            
            # Check if already exists
            existing_receipt = MoneyReceipt.objects.filter(sale=self).first()
            if existing_receipt:
                if existing_receipt.amount != self.paid_amount:
                    existing_receipt.amount = self.paid_amount
                    existing_receipt.save()
                return existing_receipt
            
            # Create new receipt
            money_receipt = MoneyReceipt(
                company=self.company,
                customer=money_receipt_customer,  # None for walk-in customers
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
            logger.info(f"Money receipt created: {money_receipt.mr_no} for {self.invoice_no}")
            return money_receipt
            
        except Exception as e:
            logger.error(f"Error creating money receipt for {self.invoice_no}: {e}")
            return None

    def clean(self):
        """Model validation"""
        super().clean()
        
        # Validate that company is set
        if not self.company:
            raise ValidationError({
                'company': 'Sale must be associated with a company.'
            })
        
        # Validate that due_amount is not negative
        if self.due_amount < 0:
            raise ValidationError({
                'due_amount': 'Due amount cannot be negative.'
            })
        
        # Validate saved customer has customer record
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError({
                'customer': 'Saved customer must have a customer record.'
            })
        
        # Validate payment method when payment is made
        if self.paid_amount > 0 and not self.payment_method:
            raise ValidationError({
                'payment_method': 'Payment method is required when payment is made.'
            })

    def __str__(self):
        return f"{self.invoice_no} - {self.get_customer_display()} - {self.get_customer_type_display()}"

    @property
    def is_walk_in_customer(self):
        return self.customer_type == 'walk_in'

    def get_customer_display(self):
        """Get customer display name - FIXED VERSION"""
        if self.customer_type == 'walk_in':
            return self.customer_name or "Walk-in Customer"
        elif self.customer:
            return self.customer.name
        else:
            return "Unknown Customer"

    def add_payment(self, amount, payment_method=None, account=None):
        """
        Add additional payment to existing sale
        """
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), null=True, blank=True)

    class Meta:
        ordering = ['id']

    def subtotal(self):
        """Calculate subtotal for this item"""
        try:
            total = Decimal(str(self.unit_price)) * self.quantity
            
            if self.discount_type == 'percent' and self.discount:
                total -= total * (Decimal(str(self.discount)) / Decimal('100.00'))
            elif self.discount_type == 'fixed' and self.discount:
                total -= Decimal(str(self.discount))
                
            return round(max(total, Decimal('0.00')), 2)
        except:
            return Decimal('0.00')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Validate stock for new items
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}, Requested: {self.quantity}"
                )
        
        # ✅ FIXED: Store old quantity for stock adjustment
        old_qty = 0
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
                old_qty = old_item.quantity
            except SaleItem.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

        # ✅ FIXED: Update product stock properly
        try:
            product = self.product
            if is_new:
                # New item - decrease stock
                product.stock_qty -= self.quantity
            else:
                # Updated item - adjust stock based on quantity change
                stock_change = self.quantity - old_qty
                product.stock_qty -= stock_change
            
            product.save(update_fields=['stock_qty'])
        except Exception as e:
            logger.error(f"Error updating product stock: {e}")
        
        # ✅ FIXED: Update sale totals
        try:
            self.sale.update_totals()
        except Exception as e:
            logger.error(f"Error updating sale totals: {e}")

    def delete(self, *args, **kwargs):
        # Restore product stock
        try:
            self.product.stock_qty += self.quantity
            self.product.save(update_fields=['stock_qty'])
        except Exception as e:
            logger.error(f"Error restoring product stock: {e}")
        
        sale = self.sale
        super().delete(*args, **kwargs)
        
        # Update sale totals after deletion
        try:
            sale.update_totals()
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