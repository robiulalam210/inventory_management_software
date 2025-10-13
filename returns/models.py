from django.db import models
from sales.models import SaleItem
from purchases.models import Purchase
from products.models import Product
from accounts.models import Account

class SalesReturn(models.Model):
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name='returns')
    qty = models.PositiveIntegerField()
    reason = models.TextField()
    return_date = models.DateField()

    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='sale_returns')
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True)
    vat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vat_type = models.CharField(max_length=50, blank=True, null=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge_type = models.CharField(max_length=50, blank=True, null=True)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Return {self.qty} of {self.sale_item}"

class PurchaseReturn(models.Model):
    purchase_ref = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='returns')
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_returns')
    quantity = models.PositiveIntegerField()
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase_returns')
    date = models.DateTimeField(auto_now_add=True)
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"PurchaseReturn {self.quantity}x {self.product_ref}"

class BadStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bad_stocks')
    qty = models.PositiveIntegerField()
    reason = models.TextField()
    date = models.DateField()

    def __str__(self):
        return f"Bad Stock {self.qty} of {self.product.name}"