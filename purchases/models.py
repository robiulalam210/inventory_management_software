# branch_warehouse/models.py - MINIMAL FIXES ONLY

from django.db import models
from django.db.models import Sum, F, Q
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)


class Purchase(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('digital', 'Digital Payment'),
    ]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_created')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_updated')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    purchase_date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_delivery_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_service_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, blank=True, null=True, related_name='purchases')
    invoice_no = models.CharField(max_length=20, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remark = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    reference_no = models.CharField(max_length=50, blank=True, null=True)
    expected_delivery_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-purchase_date', '-date_created']
        unique_together = ['company', 'invoice_no']
        indexes = [
            models.Index(fields=['company', 'purchase_date']),
            models.Index(fields=['supplier', 'payment_status']),
            models.Index(fields=['invoice_no']),
            models.Index(fields=['is_active', 'payment_status']),
            models.Index(fields=['purchase_date', 'company']),
        ]

    def __str__(self):
        return f"{self.invoice_no or 'No Invoice'} - {self.supplier.name}"

    def clean(self):
        """Validate purchase data before saving"""
        if self.paid_amount < 0:
            raise ValidationError("Paid amount cannot be negative")
        
        if self.overall_discount < 0:
            raise ValidationError("Discount cannot be negative")
            
        if self.vat < 0:
            raise ValidationError("VAT cannot be negative")
            
        if self.purchase_date > timezone.now().date():
            raise ValidationError("Purchase date cannot be in the future")

    def _update_payment_status(self):
        """Update payment status based on paid amount"""
        logger.info(f"UPDATING: Updating payment status: Paid={self.paid_amount}, Grand Total={self.grand_total}, Due={self.due_amount}")
        
        if self.payment_status == 'cancelled':
            logger.info("INFO: Purchase is cancelled, status unchanged")
            return
            
        # Don't check items if purchase doesn't have PK yet (during initial creation)
        if not self.pk:
            logger.info("INFO: Purchase not saved yet, using basic status calculation")
            if self.paid_amount <= 0:
                self.payment_status = 'pending'
            elif self.paid_amount >= self.grand_total:
                self.payment_status = 'paid'
                self.due_amount = Decimal('0.00')
            elif self.paid_amount > 0:
                self.payment_status = 'partial'
            else:
                self.payment_status = 'pending'
        else:
            # Only check items if purchase has been saved
            if self.grand_total == 0:
                # If grand total is zero but we have items, this might be a calculation issue
                try:
                    if self.items.exists():
                        logger.warning("WARNING: Grand total is 0 but purchase has items - recalculating totals")
                        self.update_totals(force_update=True)
                except ValueError:
                    # This can happen if purchase doesn't have PK yet
                    logger.warning("WARNING: Cannot check items - purchase not fully saved")
        
        # Standard payment status logic (applies to both new and existing purchases)
        if self.paid_amount <= 0:
            self.payment_status = 'pending'
            logger.info("INFO: Status set to: pending")
        
        elif self.paid_amount >= self.grand_total:
            self.payment_status = 'paid'
            self.due_amount = Decimal('0.00')  # Ensure due is zero when paid
            logger.info("SUCCESS: Status set to: paid")
        
        elif self.paid_amount > 0 and self.paid_amount < self.grand_total:
            self.payment_status = 'partial'
            logger.info("INFO: Status set to: partial")
        
        else:
            self.payment_status = 'pending'
            logger.info("INFO: Status set to: pending (fallback)")
        
        # Calculate change amount
        if self.paid_amount > self.grand_total:
            self.change_amount = self.paid_amount - self.grand_total
            logger.info(f"INFO: Change amount updated: {self.change_amount}")
        else:
            self.change_amount = Decimal('0.00')

    def _round_decimal(self, value):
        """Helper method to round decimals consistently"""
        if value is None:
            return Decimal('0.00')
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def generate_invoice_no(self):
        """Generate company-specific sequential invoice number"""
        if not self.company:
            return f"PO-1001"
            
        try:
            current_year = timezone.now().year
            
            last_purchase = Purchase.objects.filter(
                company=self.company,
                invoice_no__isnull=False,
                invoice_no__startswith=f'PO-{current_year}'
            ).order_by('-invoice_no').first()
            
            if last_purchase and last_purchase.invoice_no:
                try:
                    parts = last_purchase.invoice_no.split('-')
                    if len(parts) >= 3:
                        last_number = int(parts[2])
                        new_number = last_number + 1
                    else:
                        last_number = int(parts[1])
                        new_number = last_number + 1
                except (ValueError, IndexError):
                    existing_count = Purchase.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                new_number = 1001
                
            return f"PO-{current_year}-{new_number:04d}"
            
        except Exception as e:
            logger.error(f"ERROR: Error generating invoice number: {str(e)}")
            existing_count = Purchase.objects.filter(company=self.company).count()
            return f"PO-{1001 + existing_count}"
    
    def update_totals(self, force_update=False):
        """Update purchase totals from items"""
        if hasattr(self, '_updating_totals') and self._updating_totals:
            return True
            
        self._updating_totals = True
        logger.info(f"UPDATING: Purchase.update_totals called for purchase ID: {self.id}")
        
        try:
            # FIXED: Use item.subtotal() which includes item discounts
            items_subtotal = sum(item.subtotal() for item in self.items.all())
            subtotal = items_subtotal or Decimal('0.00')
            subtotal = self._round_decimal(subtotal)

            logger.info(f"INFO: Calculated subtotal from items (WITH item discounts): {subtotal}")

            discount_amount = Decimal('0.00')
            if self.overall_discount_type == 'percentage':
                discount_amount = subtotal * (self.overall_discount / Decimal('100.00'))
            elif self.overall_discount_type == 'fixed':
                discount_amount = min(self.overall_discount, subtotal)
            
            discount_amount = self._round_decimal(discount_amount)

            vat_amount = Decimal('0.00')
            if self.vat_type == 'percentage':
                vat_amount = subtotal * (self.vat / Decimal('100.00'))
            elif self.vat_type == 'fixed':
                vat_amount = self.vat
            vat_amount = self._round_decimal(vat_amount)

            service_amount = Decimal('0.00')
            if self.overall_service_charge_type == 'percentage':
                service_amount = subtotal * (self.overall_service_charge / Decimal('100.00'))
            elif self.overall_service_charge_type == 'fixed':
                service_amount = self.overall_service_charge
            service_amount = self._round_decimal(service_amount)

            delivery_amount = Decimal('0.00')
            if self.overall_delivery_charge_type == 'percentage':
                delivery_amount = subtotal * (self.overall_delivery_charge / Decimal('100.00'))
            elif self.overall_delivery_charge_type == 'fixed':
                delivery_amount = self.overall_delivery_charge
            delivery_amount = self._round_decimal(delivery_amount)

            total_after_discount = max(Decimal('0.00'), subtotal - discount_amount)
            grand_total = max(Decimal('0.00'), total_after_discount + vat_amount + service_amount + delivery_amount)

            needs_save = (
                self.total != subtotal or
                self.grand_total != grand_total or
                self.due_amount != max(Decimal('0.00'), grand_total - self.paid_amount) or
                force_update
            )

            if needs_save:
                self.total = subtotal
                self.grand_total = grand_total
                self.due_amount = max(Decimal('0.00'), grand_total - self.paid_amount)
                self.change_amount = max(Decimal('0.00'), self.paid_amount - grand_total)
                self._update_payment_status()

                logger.info(f"INFO: Purchase totals updated: Subtotal={subtotal}, Grand Total={grand_total}, Paid={self.paid_amount}, Due={self.due_amount}, Change={self.change_amount}")
                
                if self.pk:
                    update_fields = [
                        "total", "grand_total", "due_amount", "change_amount", 
                        "payment_status", "date_updated"
                    ]
                    super().save(update_fields=update_fields)
                    
            return True
                
        except Exception as e:
            logger.error(f"ERROR: Error updating purchase totals: {str(e)}")
            return False
        finally:
            self._updating_totals = False

    def save(self, *args, **kwargs):
        """Custom save method"""
        is_new = self.pk is None
        
        self.clean()
        
        if is_new and not self.invoice_no:
            self.invoice_no = self.generate_invoice_no()
        
        if is_new:
            self.due_amount = max(Decimal('0.00'), self.grand_total - self.paid_amount)
            self._update_payment_status()
        
        super().save(*args, **kwargs)

    def make_payment(self, amount, payment_method=None, account=None, description=None):
        """Make a payment towards this purchase"""
        amount = self._round_decimal(amount)
        
        # Validate payment
        can_pay, message = self.can_make_payment(amount)
        if not can_pay:
            raise ValueError(message)
        
        try:
            with db_transaction.atomic():
                # Calculate new values
                new_paid_amount = self.paid_amount + amount
                new_due_amount = max(Decimal('0.00'), self.grand_total - new_paid_amount)
                new_change_amount = max(Decimal('0.00'), new_paid_amount - self.grand_total)
                
                logger.info(f"UPDATING: Payment Calculation:")
                logger.info(f"  Current: Paid={self.paid_amount}, Due={self.due_amount}, Grand Total={self.grand_total}")
                logger.info(f"  Payment: Amount={amount}")
                logger.info(f"  New: Paid={new_paid_amount}, Due={new_due_amount}, Change={new_change_amount}")
                
                # Update instance fields
                self.paid_amount = new_paid_amount
                self.due_amount = new_due_amount
                self.change_amount = new_change_amount
                
                if payment_method:
                    self.payment_method = payment_method
                if account:
                    self.account = account
                    
                # Update payment status
                self._update_payment_status()
                
                # Save purchase first
                update_fields = [
                    "paid_amount", "due_amount", "change_amount", "payment_status", 
                    "date_updated"
                ]
                
                if payment_method:
                    update_fields.append("payment_method")
                if account:
                    update_fields.append("account")
                
                super().save(update_fields=update_fields)
                
                # Create transaction for the payment
                if account and amount > 0:
                    try:
                        from transactions.models import Transaction
                        
                        transaction_obj = Transaction.objects.create(
                            company=self.company,
                            transaction_type='debit',
                            amount=amount,
                            account=account,
                            payment_method=payment_method or self.payment_method,
                            description=description or f"Purchase Payment - {self.invoice_no} - {self.supplier.name}",
                            purchase=self,
                            created_by=self.updated_by or self.created_by,
                            status='completed'
                        )
                        
                        if transaction_obj:
                            logger.info(f"SUCCESS: Debit transaction created for purchase payment: {transaction_obj.transaction_no}")
                        else:
                            logger.error(f"ERROR: Transaction creation returned None")
                            
                    except Exception as e:
                        logger.error(f"ERROR: Transaction creation failed: {e}")
                        # Don't fail the payment if transaction creation fails
            
            logger.info(f"SUCCESS: Payment of {amount} applied to purchase {self.invoice_no}")
            return True
            
        except Exception as e:
            logger.error(f"ERROR: Error in make_payment: {e}")
            raise

    def create_initial_payment_transaction(self):
        """Create transaction for initial payment when purchase is created"""
        if self.paid_amount > 0 and self.account:
            try:
                from transactions.models import Transaction
                
                transaction_obj = Transaction.objects.create(
                    company=self.company,
                    transaction_type='debit',
                    amount=self.paid_amount,
                    account=self.account,
                    payment_method=self.payment_method,
                    description=f"Purchase Payment - {self.invoice_no} - {self.supplier.name}",
                    purchase=self,
                    created_by=self.created_by,
                    status='completed'
                )
                
                if transaction_obj:
                    logger.info(f"SUCCESS: Initial debit transaction created: {transaction_obj.transaction_no}")
                    return transaction_obj
                    
            except Exception as e:
                logger.error(f"ERROR: Error creating initial transaction: {e}")
        
        return None

    def cancel_purchase(self, reason=None):
        """Cancel the purchase and reverse stock changes"""
        if self.payment_status == 'cancelled':
            raise ValueError("Purchase is already cancelled")
            
        try:
            with db_transaction.atomic():
                # Reverse stock for all items
                for item in self.items.all():
                    item.product.stock_qty -= item.qty
                    item.product.save()
                    
                # Reverse any payments made
                if self.paid_amount > 0 and self.account:
                    try:
                        from transactions.models import Transaction
                        Transaction.objects.create(
                            company=self.company,
                            transaction_type='credit',
                            amount=self.paid_amount,
                            account=self.account,
                            payment_method=self.payment_method,
                            description=f"Purchase Cancellation - {self.invoice_no} - {reason or 'No reason provided'}",
                            purchase=self,
                            created_by=self.updated_by or self.created_by,
                            status='completed'
                        )
                        
                        self.account.balance += self.paid_amount
                        self.account.save(update_fields=['balance', 'updated_at'])
                    except Exception as e:
                        logger.error(f"ERROR: Error reversing payment during cancellation: {e}")
                
                self.payment_status = 'cancelled'
                self.is_active = False
                self.save(update_fields=['payment_status', 'is_active', 'date_updated'])
                
            logger.info(f"SUCCESS: Purchase {self.invoice_no} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(f"ERROR: Error cancelling purchase: {e}")
            raise

    def add_items(self, items_data):
        """Add multiple items to the purchase at once"""
        from .models import PurchaseItem
        
        created_items = []
        for item_data in items_data:
            try:
                item = PurchaseItem.objects.create(
                    purchase=self,
                    **item_data
                )
                created_items.append(item)
            except Exception as e:
                logger.error(f"ERROR: Error creating purchase item: {e}")
                continue
        
        self.update_totals()
        return created_items

    def instant_pay(self, payment_method, account, paid_amount=None):
        """
        Process instant payment for purchase
        """
        if paid_amount is None:
            paid_amount = self.due_amount
        
        if paid_amount > 0 and account and payment_method:
            logger.info(f"INFO: Processing instant payment: {paid_amount} via {payment_method}")
            try:
                from transactions.models import Transaction
                transaction = Transaction.create_for_purchase_payment(
                    purchase=self,
                    amount=paid_amount,
                    payment_method=payment_method,
                    account=account,
                    created_by=self.created_by
                )
                
                if transaction:
                    logger.info(f"SUCCESS: Instant payment transaction created: {transaction.transaction_no}")
                    # Refresh purchase to get updated paid_amount
                    self.refresh_from_db()
                    return transaction
                else:
                    logger.error("ERROR: Transaction creation returned None")
                    return None
                    
            except Exception as e:
                logger.error(f"ERROR: Error in instant_pay: {str(e)}")
                raise
        else:
            logger.warning(f"WARNING: Instant pay skipped - paid_amount: {paid_amount}, account: {account}, payment_method: {payment_method}")
            return None

    def apply_partial_payment(self, amount, payment_method=None, account=None):
        """Apply partial payment with proper validation"""
        amount = self._round_decimal(amount)
        
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if amount > self.due_amount:
            amount = self.due_amount
            logger.info(f"WARNING: Payment amount adjusted to due amount: {amount}")
        
        return self.make_payment(amount, payment_method, account)

    def apply_full_payment(self, payment_method=None, account=None):
        """Pay the remaining due amount"""
        if self.due_amount > 0:
            return self.make_payment(self.due_amount, payment_method, account)
        else:
            logger.info(f"WARNING: No due amount for full payment on purchase {self.invoice_no}")
            return False

    def apply_overpayment(self, amount, payment_method=None, account=None):
        """Apply payment that might be more than due amount"""
        amount = self._round_decimal(amount)
        
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if amount > self.due_amount:
            overpayment_amount = amount - self.due_amount
            logger.info(f"INFO: Overpayment detected: {overpayment_amount} on purchase {self.invoice_no}")
        
        return self.make_payment(amount, payment_method, account)

    def get_payment_breakdown(self):
        """Get detailed payment breakdown for API responses"""
        return {
            'invoice_no': self.invoice_no,
            'grand_total': float(self.grand_total),
            'paid_amount': float(self.paid_amount),
            'due_amount': float(self.due_amount),
            'change_amount': float(self.change_amount),
            'payment_status': self.payment_status,
            'payment_progress': self.payment_progress,
            'is_overpaid': self.is_overpaid,
            'is_fully_paid': self.payment_status == 'paid',
            'is_partially_paid': self.payment_status == 'partial',
            'is_cancelled': self.payment_status == 'cancelled',
            'remaining_balance': float(self.due_amount),
            'overpayment_amount': float(self.change_amount) if self.is_overpaid else 0.0,
            'supplier_name': self.supplier.name,
            'purchase_date': self.purchase_date.isoformat(),
        }

    def can_make_payment(self, amount=None):
        """Check if payment can be made"""
        if self.payment_status == 'cancelled':
            return False, "Cannot make payment on cancelled purchase"
            
        if self.payment_status == 'paid' and not amount:
            return False, "Purchase is already fully paid"
        
        if amount and amount <= 0:
            return False, "Payment amount must be greater than 0"
        
        if amount and amount > (self.due_amount + Decimal('1000')):
            return False, f"Payment amount exceeds reasonable overpayment limit"
        
        return True, "Payment can be processed"

    def reset_payment(self):
        """Reset all payment information (for testing/error recovery)"""
        if self.payment_status == 'cancelled':
            raise ValueError("Cannot reset payment for cancelled purchase")
            
        self.paid_amount = Decimal('0.00')
        self.due_amount = self.grand_total
        self.change_amount = Decimal('0.00')
        self.payment_status = 'pending'
        self.payment_method = None
        self.account = None
        
        update_fields = [
            "paid_amount", "due_amount", "change_amount", "payment_status",
            "payment_method", "account", "date_updated"
        ]
        super().save(update_fields=update_fields)
        
        logger.info(f"INFO: Payment reset for purchase {self.invoice_no}")

    @property
    def is_overpaid(self):
        return self.paid_amount > self.grand_total

    @property
    def payment_progress(self):
        """Get payment progress percentage"""
        if self.grand_total == 0:
            return 0
        progress = (self.paid_amount / self.grand_total) * 100
        return float(min(100, progress))

    @property
    def item_count(self):
        """Get total number of items in this purchase"""
        return self.items.count()

    @property
    def total_quantity(self):
        """Get total quantity of all items"""
        return self.items.aggregate(total_qty=Sum('qty'))['total_qty'] or 0

    @classmethod
    def get_due_purchases(cls, supplier=None, company=None):
        """Get all due purchases for a supplier or company"""
        queryset = cls.objects.filter(due_amount__gt=0, is_active=True)
        
        if supplier:
            queryset = queryset.filter(supplier=supplier)
        if company:
            queryset = queryset.filter(company=company)
            
        return queryset.order_by('purchase_date')

    @classmethod
    def get_company_purchases(cls, company, start_date=None, end_date=None):
        """Get purchases for a company within date range"""
        queryset = cls.objects.filter(company=company, is_active=True)
        
        if start_date:
            queryset = queryset.filter(purchase_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(purchase_date__lte=end_date)
            
        return queryset.order_by('-purchase_date')


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    
    batch_no = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['purchase', 'product']),
            models.Index(fields=['product', 'batch_no']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.qty}"

    def clean(self):
        """Validate item data"""
        if self.price < 0:
            raise ValidationError("Price cannot be negative")
        if self.qty <= 0:
            raise ValidationError("Quantity must be greater than 0")
        if self.discount < 0:
            raise ValidationError("Discount cannot be negative")
        if self.expiry_date and self.expiry_date < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past")

    def subtotal(self):
        """Calculate item subtotal with proper rounding"""
        try:
            total = self.qty * self.price
            
            if self.discount_type == 'percentage':
                discount_amount = total * (self.discount / Decimal('100.00'))
            elif self.discount_type == 'fixed':
                discount_amount = self.discount
            else:
                discount_amount = Decimal('0.00')
            
            # Ensure discount doesn't exceed total
            discount_amount = min(discount_amount, total)
            
            final_total = max(Decimal('0.00'), total - discount_amount)
            return final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.error(f"ERROR: Error calculating subtotal: {str(e)}")
            return Decimal('0.00')

    def save(self, *args, **kwargs):
        """Custom save with stock management"""
        is_new = self.pk is None
        old_qty = 0
        
        self.clean()
        
        if not is_new:
            try:
                old_item = PurchaseItem.objects.get(pk=self.pk)
                old_qty = old_item.qty
            except PurchaseItem.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        try:
            if self.price > 0:
                product = self.product
                if is_new:
                    product.stock_qty += self.qty
                else:
                    stock_change = self.qty - old_qty
                    product.stock_qty += stock_change
                
                product.save()
                
                if not hasattr(self.purchase, '_updating_totals'):
                    self.purchase.update_totals()
            
        except Exception as e:
            logger.error(f"ERROR: Error in PurchaseItem.save: {str(e)}")
            raise

    def delete(self, *args, **kwargs):
        """Custom delete with stock management"""
        purchase = self.purchase
        product = self.product
        
        try:
            product.stock_qty -= self.qty
            product.save()
            
            super().delete(*args, **kwargs)
            
            purchase.update_totals()
            
        except Exception as e:
            logger.error(f"ERROR: Error in PurchaseItem.delete: {str(e)}")
            raise

    def get_item_summary(self):
        """Get item summary for API responses"""
        return {
            'id': self.id,
            'product_id': self.product.id,
            'product_name': self.product.name,
            'qty': self.qty,
            'price': float(self.price),
            'discount': float(self.discount),
            'discount_type': self.discount_type,
            'subtotal': float(self.subtotal()),
            'batch_no': self.batch_no,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
        }