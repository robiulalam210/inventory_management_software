from django.db import models
from products.models import Product
from accounts.models import Account
from core.models import Company
from suppliers.models import Supplier



class Purchase(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField()
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_charge_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percentage','Percentage')), default='fixed')
    payment_method = models.CharField(max_length=100, blank=True, null=True)  # or use choices if needed
    account = models.ForeignKey( Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase')
    invoice_no = models.CharField(max_length=20, blank=True, null=True, unique=True)
    payment_status = models.CharField(max_length=20, default='pending')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.invoice_no:
            self.invoice_no = f"PO-{1000 + self.id}"
            super().save(update_fields=['invoice_no'])

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

    def __str__(self):
        return f"{self.product.name} x {self.qty}"