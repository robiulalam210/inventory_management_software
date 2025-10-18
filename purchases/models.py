from django.db import models
from products.models import Product
from accounts.models import Account
from core.models import Company
from suppliers.models import Supplier

class Purchase(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # New field
    date = models.DateField()
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase')
    invoice_no = models.CharField(max_length=20, blank=True, null=True, unique=True)
    payment_status = models.CharField(max_length=20, default='pending')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.invoice_no:
            self.invoice_no = f"PO-{1000 + self.id}"
            super().save(update_fields=['invoice_no'])

    def update_totals(self):
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

        super().save(update_fields=["total", "grand_total"])

    def __str__(self):
        return f"{self.invoice_no or ''} - {self.supplier.name}"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')

    def subtotal(self):
        total = self.qty * self.price
        if self.discount_type == 'percentage':
            total -= total * (self.discount / 100)
        elif self.discount_type == 'fixed':
            total -= self.discount
        return round(total, 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            product = self.product
            product.stock_qty += self.qty  # Increase stock
            product.save(update_fields=['stock_qty'])
        
        # Update purchase totals
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