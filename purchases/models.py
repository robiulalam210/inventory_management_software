# purchases/models.py
from django.db import models
from products.models import Product
from accounts.models import Account
from core.models import Company
from suppliers.models import Supplier
from django.conf import settings
from django.utils import timezone

class Purchase(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    
    # ✅ AUTO User & Date Fields
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_created')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases_updated')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    # Purchase Details
    purchase_date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # ✅ Payment Tracking
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Charges and Discounts
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    
    # Payment Information
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchases')
    invoice_no = models.CharField(max_length=20, blank=True, null=True, unique=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remark = models.TextField(blank=True, null=True)

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

    def update_totals(self):
        """Update purchase totals from items"""
        print(f"🔄 Purchase.update_totals called for purchase ID: {self.id}")
        
        items = self.items.all()
        subtotal = sum([item.subtotal() for item in items])

        # Calculate overall discount
        discount_amount = 0
        if self.overall_discount_type == 'percentage':
            discount_amount = subtotal * (self.overall_discount / 100)
        elif self.overall_discount_type == 'fixed':
            discount_amount = self.overall_discount

        # Calculate charges on SUBTOTAL amount
        vat_amount = 0
        if self.vat_type == 'percentage':
            vat_amount = subtotal * (self.vat / 100)
        elif self.vat_type == 'fixed':
            vat_amount = self.vat

        service_amount = 0
        if self.overall_service_charge_type == 'percentage':
            service_amount = subtotal * (self.overall_service_charge / 100)
        elif self.overall_service_charge_type == 'fixed':
            service_amount = self.overall_service_charge

        delivery_amount = 0
        if self.overall_delivery_charge_type == 'percentage':
            delivery_amount = subtotal * (self.overall_delivery_charge / 100)
        elif self.overall_delivery_charge_type == 'fixed':
            delivery_amount = self.overall_delivery_charge

        # Calculate totals
        total_after_discount = subtotal - discount_amount
        grand_total = total_after_discount + vat_amount + service_amount + delivery_amount

        self.total = round(subtotal, 2)
        self.grand_total = round(grand_total, 2)
        
        # Recalculate due amount
        self.due_amount = max(0, self.grand_total - self.paid_amount)
        self.change_amount = max(0, self.paid_amount - self.grand_total)
        self._update_payment_status()

        print(f"📊 Purchase totals updated: Total={self.total}, Grand Total={self.grand_total}, Due={self.due_amount}")
        
        super().save(update_fields=[
            "total", "grand_total", "due_amount", "change_amount", "payment_status"
        ])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Calculate due amount before saving
        self.due_amount = max(0, self.grand_total - self.paid_amount)
        self.change_amount = max(0, self.paid_amount - self.grand_total)
        
        # Update payment status
        self._update_payment_status()
        
        super().save(*args, **kwargs)
        
        # Auto-generate invoice number after saving for new purchases
        if is_new and not self.invoice_no:
            self.invoice_no = f"PO-{1000 + self.id}"
            super().save(update_fields=['invoice_no'])
        
        # Update supplier totals after saving - with transaction safety
        if self.supplier:
            print(f"🔄 Purchase.save: Calling supplier update for supplier ID {self.supplier_id}")
            try:
                # Import inside to avoid circular imports
                from suppliers.models import Supplier
                
                # Get fresh supplier instance to ensure we have latest data
                supplier = Supplier.objects.get(id=self.supplier_id)
                
                if hasattr(supplier, 'update_purchase_totals'):
                    print(f"   ✅ Calling update_purchase_totals for '{supplier.name}'")
                    supplier.update_purchase_totals()
                else:
                    print(f"❌ WARNING: Supplier has no update_purchase_totals method")
                    
            except Exception as e:
                print(f"❌ ERROR updating supplier totals: {e}")

    def make_payment(self, amount, payment_method=None, account=None):
        """Make a payment towards this purchase"""
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        self.paid_amount += amount
        
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
            
        self.save()
        
        # Update account balance if account is provided
        if account and amount > 0:
            account.balance -= amount  # Decrease balance for purchase payment
            account.save(update_fields=['balance'])

    def instant_pay(self, payment_method, account):
        """Instant payment - pay the full grand total"""
        if self.grand_total > 0:
            self.make_payment(self.grand_total, payment_method, account)

    @property
    def is_overpaid(self):
        return self.paid_amount > self.grand_total

    @property
    def payment_progress(self):
        """Get payment progress percentage"""
        if self.grand_total == 0:
            return 0
        return min(100, (self.paid_amount / self.grand_total) * 100)

    def __str__(self):
        return f"{self.invoice_no or 'No Invoice'} - {self.supplier.name}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    
    # ✅ Auto fields
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def subtotal(self):
        total = self.qty * self.price
        if self.discount_type == 'percentage':
            total -= total * (self.discount / 100)
        elif self.discount_type == 'fixed':
            total -= self.discount
        return round(total, 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_qty = 0
        
        # Get old quantity if updating
        if not is_new:
            try:
                old_item = PurchaseItem.objects.get(pk=self.pk)
                old_qty = old_item.qty
            except PurchaseItem.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Update product stock
        product = self.product
        if is_new:
            # New item - increase stock
            product.stock_qty += self.qty
        else:
            # Updated item - adjust stock based on quantity change
            stock_change = self.qty - old_qty
            product.stock_qty += stock_change
        
        product.save(update_fields=['stock_qty'])
        
        # Update purchase totals
        print(f"🔄 PurchaseItem.save: Calling update_totals for purchase ID: {self.purchase.id}")
        self.purchase.update_totals()

    def delete(self, *args, **kwargs):
        # Decrease stock when item is deleted
        self.product.stock_qty -= self.qty
        self.product.save(update_fields=['stock_qty'])
        
        purchase = self.purchase
        super().delete(*args, **kwargs)
        purchase.update_totals()

    def __str__(self):
        return f"{self.product.name} x {self.qty}"