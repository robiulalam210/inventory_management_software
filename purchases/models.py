from django.db import models
from django.db.models import Sum, F
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

class Purchase(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('digital', 'Digital Payment'),
    ]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE)
    
    # ✅ AUTO User & Date Fields
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_created')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_updated')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    # Purchase Details
    purchase_date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # ✅ Payment Tracking
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Charges and Discounts
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_delivery_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_service_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    
    # Payment Information
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, blank=True, null=True, related_name='purchases')
    invoice_no = models.CharField(max_length=20, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remark = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-purchase_date', '-date_created']
        # ✅ Add unique constraint to prevent duplicate invoice numbers
        unique_together = ['company', 'invoice_no']
        indexes = [
            models.Index(fields=['company', 'purchase_date']),
            models.Index(fields=['supplier', 'payment_status']),
            models.Index(fields=['invoice_no']),
        ]

    def __str__(self):
        return f"{self.invoice_no or 'No Invoice'} - {self.supplier.name}"

    def _update_payment_status(self):
        """Update payment status based on paid amount"""
        if self.paid_amount == 0:
            self.payment_status = 'pending'
        elif self.paid_amount >= self.grand_total:
            self.payment_status = 'paid'
        elif self.paid_amount > 0 and self.paid_amount < self.grand_total:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'

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
            # Get the last invoice number for this company
            last_purchase = Purchase.objects.filter(
                company=self.company,
                invoice_no__isnull=False,
                invoice_no__startswith='PO-'
            ).order_by('-invoice_no').first()
            
            if last_purchase and last_purchase.invoice_no:
                try:
                    # Extract number from "PO-1001" format
                    last_number = int(last_purchase.invoice_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing purchases
                    existing_count = Purchase.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First purchase for this company
                existing_count = Purchase.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            return f"PO-{new_number}"
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {str(e)}")
            # Fallback: simple count-based numbering
            existing_count = Purchase.objects.filter(company=self.company).count()
            return f"PO-{1001 + existing_count}"

    def update_totals(self):
        """Update purchase totals from items - FIXED VERSION"""
        logger.info(f"🔄 Purchase.update_totals called for purchase ID: {self.id}")
        
        try:
            items = self.items.all()
            subtotal = sum([item.subtotal() for item in items])
            subtotal = self._round_decimal(subtotal)

            # Calculate overall discount - FIXED: Don't allow discount to exceed subtotal
            discount_amount = Decimal('0.00')
            if self.overall_discount_type == 'percentage':
                discount_amount = subtotal * (self.overall_discount / Decimal('100.00'))
            elif self.overall_discount_type == 'fixed':
                discount_amount = min(self.overall_discount, subtotal)  # Don't allow negative totals
            
            discount_amount = self._round_decimal(discount_amount)

            # Calculate charges on SUBTOTAL amount
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

            # Calculate totals - FIXED: Ensure no negative totals
            total_after_discount = max(Decimal('0.00'), subtotal - discount_amount)
            grand_total = max(Decimal('0.00'), total_after_discount + vat_amount + service_amount + delivery_amount)

            # Update fields
            self.total = subtotal
            self.grand_total = grand_total
            
            # Recalculate due amount
            self.due_amount = max(Decimal('0.00'), self.grand_total - self.paid_amount)
            self.change_amount = max(Decimal('0.00'), self.paid_amount - self.grand_total)
            self._update_payment_status()

            logger.info(f"📊 Purchase totals updated: Subtotal={subtotal}, Discount={discount_amount}, Grand Total={grand_total}, Due={self.due_amount}")
            
            # Save only if instance already exists
            if self.pk:
                super().save(update_fields=[
                    "total", "grand_total", "due_amount", "change_amount", "payment_status", "date_updated"
                ])
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating purchase totals: {str(e)}")
            return False

    def save(self, *args, **kwargs):
        """Custom save method to handle invoice generation - FIXED VERSION"""
        is_new = self.pk is None
        
        # ✅ FIXED: Remove custom kwargs before calling super().save()
        # Extract our custom parameter and remove it from kwargs
        should_update_totals = kwargs.pop('update_totals', True)
        
        # Generate invoice number for new purchases
        if is_new and not self.invoice_no:
            self.invoice_no = self.generate_invoice_no()
        
        # Validate data before saving
        if self.paid_amount < 0:
            raise ValueError("Paid amount cannot be negative")
        
        # SAVE FIRST to get PK
        super().save(*args, **kwargs)
        
        # Update totals after save (this will save again with update_fields)
        if is_new or should_update_totals:
            self.update_totals()
        
        # Update supplier totals
        if self.supplier:
            logger.info(f"🔄 Purchase.save: Triggering supplier update for '{self.supplier.name}'")
            try:
                self.supplier.update_purchase_totals()
            except Exception as e:
                logger.error(f"❌ ERROR updating supplier totals: {e}")

    def make_payment(self, amount, payment_method=None, account=None):
        """Make a payment towards this purchase - FIXED VERSION"""
        amount = self._round_decimal(amount)
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if amount > self.due_amount:
            raise ValueError(f"Payment amount ({amount}) exceeds due amount ({self.due_amount})")
        
        self.paid_amount += amount
        
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
            
        # ✅ FIXED: Save without triggering full update_totals
        # We'll handle the totals update manually
        update_fields = ["paid_amount", "due_amount", "change_amount", "payment_status", "date_updated"]
        if payment_method:
            update_fields.append("payment_method")
        if account:
            update_fields.append("account")
            
        # Update payment status
        self._update_payment_status()
        
        # Save with specific fields to avoid recursion
        super().save(update_fields=update_fields)
        
        # Update account balance if account is provided
        if account and amount > 0:
            account.balance -= amount  # Decrease balance for purchase payment
            account.save(update_fields=['balance'])
            
        logger.info(f"✅ Payment of {amount} applied to purchase {self.invoice_no}")
        return True

    def apply_supplier_payment(self, amount):
        """
        Apply payment from SupplierPayment model
        This is called when a SupplierPayment is created for this purchase
        """
        amount = self._round_decimal(amount)
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if amount > self.due_amount:
            raise ValueError(f"Payment amount ({amount}) exceeds due amount ({self.due_amount})")
        
        # Update paid amount and recalculate due amount
        self.paid_amount += amount
        self.due_amount = max(0, self.grand_total - self.paid_amount)
        self._update_payment_status()
        
        # Save without triggering the supplier update again
        update_fields = ["paid_amount", "due_amount", "payment_status", "date_updated"]
        super().save(update_fields=update_fields)
        
        logger.info(f"✅ Supplier payment applied: {amount} to purchase {self.invoice_no}")
        return True

    def instant_pay(self, payment_method, account):
        """Instant payment - pay the full grand total - FIXED VERSION"""
        if self.grand_total > 0:
            # ✅ FIXED: Use the make_payment method directly
            return self.make_payment(self.grand_total, payment_method, account)
        return False

    def get_payment_summary(self):
        """Get payment summary for API responses"""
        return {
            'invoice_no': self.invoice_no,
            'grand_total': float(self.grand_total),
            'paid_amount': float(self.paid_amount),
            'due_amount': float(self.due_amount),
            'payment_status': self.payment_status,
            'payment_progress': self.payment_progress,
            'is_overpaid': self.is_overpaid,
            'supplier_name': self.supplier.name,
            'purchase_date': self.purchase_date.isoformat()
        }

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

    @classmethod
    def get_due_purchases(cls, supplier=None, company=None):
        """Get all due purchases for a supplier or company"""
        queryset = cls.objects.filter(due_amount__gt=0)
        
        if supplier:
            queryset = queryset.filter(supplier=supplier)
        if company:
            queryset = queryset.filter(company=company)
            
        return queryset.order_by('purchase_date')

    @classmethod
    def get_company_purchases(cls, company, start_date=None, end_date=None):
        """Get purchases for a company within date range"""
        queryset = cls.objects.filter(company=company)
        
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
    
    # ✅ Auto fields
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['purchase', 'product']),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.qty}"

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
                
            # Don't allow negative subtotals
            final_total = max(Decimal('0.00'), total - discount_amount)
            return final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.error(f"Error calculating subtotal: {str(e)}")
            return Decimal('0.00')

    def clean(self):
        """Validate item data"""
        from django.core.exceptions import ValidationError
        
        if self.price < 0:
            raise ValidationError("Price cannot be negative")
        if self.qty <= 0:
            raise ValidationError("Quantity must be greater than 0")
        if self.discount < 0:
            raise ValidationError("Discount cannot be negative")

    def save(self, *args, **kwargs):
        """Custom save with stock management - FIXED VERSION"""
        is_new = self.pk is None
        old_qty = 0
        
        # Validate data
        self.clean()
        
        # Get old quantity if updating
        if not is_new:
            try:
                old_item = PurchaseItem.objects.get(pk=self.pk)
                old_qty = old_item.qty
            except PurchaseItem.DoesNotExist:
                pass
        
        # Save the item
        super().save(*args, **kwargs)
        
        try:
            # Update product stock
            product = self.product
            if is_new:
                # New item - increase stock
                product.stock_qty += self.qty
            else:
                # Updated item - adjust stock based on quantity change
                stock_change = self.qty - old_qty
                product.stock_qty += stock_change
            
            # ✅ FIXED: Use 'updated_at' instead of 'date_updated' for Product model
            product.save(update_fields=['stock_qty', 'updated_at'])
            
            # Update purchase totals
            logger.info(f"🔄 PurchaseItem.save: Calling update_totals for purchase ID: {self.purchase.id}")
            self.purchase.update_totals()
            
        except Exception as e:
            logger.error(f"❌ Error in PurchaseItem.save: {str(e)}")
            # If there's still an error, try saving without update_fields
            try:
                self.product.save()
                logger.info("✅ Product saved without update_fields as fallback")
            except Exception as final_error:
                logger.error(f"❌ Final error saving product: {final_error}")
            raise

    def delete(self, *args, **kwargs):
        """Custom delete with stock management - FIXED VERSION"""
        # Store purchase reference before deletion
        purchase = self.purchase
        
        try:
            # Decrease stock when item is deleted
            self.product.stock_qty -= self.qty
            
            # ✅ FIXED: Use 'updated_at' instead of 'date_updated' for Product model
            self.product.save(update_fields=['stock_qty', 'updated_at'])
            
            super().delete(*args, **kwargs)
            
            # Update purchase totals after deletion
            purchase.update_totals()
            
        except Exception as e:
            logger.error(f"❌ Error in PurchaseItem.delete: {str(e)}")
            # If there's still an error, try saving without update_fields
            try:
                self.product.save()
                logger.info("✅ Product saved without update_fields as fallback in delete")
            except Exception as final_error:
                logger.error(f"❌ Final error saving product in delete: {final_error}")
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
            'subtotal': float(self.subtotal())
        }


# Signal handlers for better integration
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=PurchaseItem)
def purchase_item_post_save(sender, instance, created, **kwargs):
    """Signal to update purchase totals after item save"""
    try:
        if not created:  # Only update if it's not a new purchase (purchase already handles new items)
            instance.purchase.update_totals()
    except Exception as e:
        logger.error(f"Error updating purchase totals after item save: {e}")

@receiver(post_delete, sender=PurchaseItem)
def purchase_item_post_delete(sender, instance, **kwargs):
    """Signal to update purchase totals after item delete"""
    try:
        instance.purchase.update_totals()
    except Exception as e:
        logger.error(f"Error updating purchase totals after item delete: {e}")