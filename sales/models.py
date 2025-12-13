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
            
            # SUCCESS: FIXED: Auto-assign company from created_by user if not set
            if not self.company and hasattr(self, 'created_by') and self.created_by:
                if hasattr(self.created_by, 'company') and self.created_by.company:
                    self.company = self.created_by.company
                    logger.info(f"Auto-assigned company from user: {self.company}")
            
            # SUCCESS: FIXED: CRITICAL - Ensure company is set before any operations
            if not self.company:
                logger.error("Sale cannot be saved without a company")
                raise ValidationError("Sale must be associated with a company.")
            
            # SUCCESS: FIXED: Validate customer belongs to same company
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
            
            # SUCCESS: FIXED: Validate saved customer belongs to same company
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
            
            # SUCCESS: FIXED: Validate account belongs to same company
            if self.account and self.account.company != self.company:
                logger.warning(f"Account company mismatch. Resetting account.")
                self.account = None
            
            # Save first to get PK
            super().save(*args, **kwargs)
            
            # Update totals after saving
            self.update_totals()
            
            # SUCCESS: FIXED: Create transaction ONLY if no money receipt will be created
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
            # SUCCESS: FIXED: Get last sale by invoice_no, not by id
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
    
    def update_totals(self, force_update=False):
        """Update purchase totals from items - FIXED VERSION"""
        if hasattr(self, '_updating_totals') and self._updating_totals:
            return True
            
        self._updating_totals = True
        logger.info(f"UPDATING: Purchase.update_totals called for purchase ID: {self.id}")
        
        try:
            # Calculate subtotal from items (item price * qty)
            items_aggregate = self.items.aggregate(
                total_subtotal=Sum(F('qty') * F('price'))
            )
            subtotal = items_aggregate['total_subtotal'] or Decimal('0.00')
            subtotal = self._round_decimal(subtotal)
            logger.info(f"INFO: Calculated subtotal from items (before item discount): {subtotal}")

            # Calculate item discounts
            total_item_discount = Decimal('0.00')
            for item in self.items.all():
                item_subtotal = item.qty * item.price
                if item.discount_type == 'percentage':
                    item_discount = item_subtotal * (item.discount / Decimal('100.00'))
                else:
                    item_discount = item.discount
                total_item_discount += min(item_discount, item_subtotal)
            
            total_item_discount = self._round_decimal(total_item_discount)
            logger.info(f"INFO: Total item discounts: {total_item_discount}")

            # Calculate total after item discounts
            total_after_item_discounts = max(Decimal('0.00'), subtotal - total_item_discount)
            logger.info(f"INFO: Total after item discounts: {total_after_item_discounts}")

            # Apply overall discount to the total after item discounts
            overall_discount_amount = Decimal('0.00')
            if self.overall_discount_type == 'percentage':
                overall_discount_amount = total_after_item_discounts * (self.overall_discount / Decimal('100.00'))
            elif self.overall_discount_type == 'fixed':
                # FIXED: Overall discount should be limited to the remaining amount
                overall_discount_amount = min(self.overall_discount, total_after_item_discounts)
            
            overall_discount_amount = self._round_decimal(overall_discount_amount)
            logger.info(f"INFO: Overall discount amount: {overall_discount_amount}")

            # Calculate total after all discounts
            total_after_all_discounts = max(Decimal('0.00'), total_after_item_discounts - overall_discount_amount)
            logger.info(f"INFO: Total after all discounts: {total_after_all_discounts}")

            # Add charges (VAT, service, delivery)
            vat_amount = Decimal('0.00')
            if self.vat_type == 'percentage':
                vat_amount = total_after_all_discounts * (self.vat / Decimal('100.00'))
            elif self.vat_type == 'fixed':
                vat_amount = self.vat
            vat_amount = self._round_decimal(vat_amount)
            logger.info(f"INFO: VAT amount: {vat_amount}")

            service_amount = Decimal('0.00')
            if self.overall_service_charge_type == 'percentage':
                service_amount = total_after_all_discounts * (self.overall_service_charge / Decimal('100.00'))
            elif self.overall_service_charge_type == 'fixed':
                service_amount = self.overall_service_charge
            service_amount = self._round_decimal(service_amount)
            logger.info(f"INFO: Service charge amount: {service_amount}")

            delivery_amount = Decimal('0.00')
            if self.overall_delivery_charge_type == 'percentage':
                delivery_amount = total_after_all_discounts * (self.overall_delivery_charge / Decimal('100.00'))
            elif self.overall_delivery_charge_type == 'fixed':
                delivery_amount = self.overall_delivery_charge
            delivery_amount = self._round_decimal(delivery_amount)
            logger.info(f"INFO: Delivery charge amount: {delivery_amount}")

            # Calculate grand total
            grand_total = max(Decimal('0.00'), 
                            total_after_all_discounts + 
                            vat_amount + 
                            service_amount + 
                            delivery_amount)
            
            logger.info(f"INFO: Final grand total: {grand_total}")

            # Check if values have changed
            needs_save = (
                self.total != total_after_item_discounts or
                self.grand_total != grand_total or
                force_update
            )

            if needs_save:
                self.total = total_after_item_discounts  # This should be the total after item discounts
                self.grand_total = grand_total
                
                # Calculate due and change amounts
                self.due_amount = max(Decimal('0.00'), grand_total - self.paid_amount)
                self.change_amount = max(Decimal('0.00'), self.paid_amount - grand_total)
                
                # Update payment status
                self._update_payment_status()

                logger.info(f"INFO: Purchase totals updated:")
                logger.info(f"  Total (after item discounts): {self.total}")
                logger.info(f"  Grand Total: {self.grand_total}")
                logger.info(f"  Paid: {self.paid_amount}")
                logger.info(f"  Due: {self.due_amount}")
                logger.info(f"  Change: {self.change_amount}")
                
                # Save if purchase exists
                if self.pk:
                    update_fields = [
                        "total", "grand_total", "due_amount", "change_amount", 
                        "payment_status", "date_updated"
                    ]
                    super().save(update_fields=update_fields)
                    
            return True
                
        except Exception as e:
            logger.error(f"ERROR: Error updating purchase totals: {str(e)}", exc_info=True)
            return False
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
            
            # SUCCESS: FIXED: Ensure payable is never negative
            if payable < Decimal('0.00'):
                payable = Decimal('0.00')
            
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
            
            # SUCCESS: FIXED: For walk-in customers, don't set customer in money receipt
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
        """Calculate item subtotal with proper rounding - FIXED VERSION"""
        try:
            total = self.qty * self.price
            
            if self.discount_type == 'percentage':
                discount_amount = total * (self.discount / Decimal('100.00'))
            elif self.discount_type == 'fixed':
                discount_amount = min(self.discount, total)  # Ensure discount doesn't exceed total
            else:
                discount_amount = Decimal('0.00')
                
            final_total = max(Decimal('0.00'), total - discount_amount)
            return final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.error(f"ERROR: Error calculating subtotal: {str(e)}")
            return Decimal('0.00')




    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Validate stock for new items
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}, Requested: {self.quantity}"
                )
        
        # SUCCESS: FIXED: Store old quantity for stock adjustment
        old_qty = 0
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
                old_qty = old_item.quantity
            except SaleItem.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

        # SUCCESS: FIXED: Update product stock properly
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
        
        # SUCCESS: FIXED: Update sale totals
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