from django.db import models
from core.models import Company
from sales.models import Sale, SaleItem
from purchases.models import Purchase
from products.models import Product
from accounts.models import Account
from datetime import date  # for default DateField if needed


# -----------------------------
# Sales Return
class SalesReturn(models.Model):
    reason = models.TextField()
    return_date = models.DateField(auto_now_add=True)  # automatically set
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='sale_returns')
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_type = models.CharField(max_length=50, blank=True, null=True)
    delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_charge_type = models.CharField(max_length=50, blank=True, null=True)
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge_type = models.CharField(max_length=50, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"SalesReturn #{self.id} - {self.invoice_no or 'No Invoice'}"


class SalesReturnItem(models.Model):
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.product_name} (x{self.quantity})"


# Purchase Return
# -----------------------------
class PurchaseReturn(models.Model):
    purchase_ref = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='returns')
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase_returns')
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge_type = models.CharField(max_length=50, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"PurchaseReturn #{self.id} - Purchase {self.purchase_ref.invoice_no or self.purchase_ref.id}"


class PurchaseReturnItem(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    qty = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.product_name} x {self.qty}"


# -----------------------------
# Bad Stock
# -----------------------------
class BadStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bad_stocks')
    qty = models.PositiveIntegerField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Bad Stock {self.qty} of {self.product.name}"
