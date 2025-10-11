# core/models.py
from django.db import models
from sales.models import SaleItem
from purchases.models import Purchase
from products.models import Product

class SalesReturn(models.Model):
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name='returns')
    qty = models.PositiveIntegerField()
    reason = models.TextField()
    date = models.DateField(auto_now_add=False)

    def __str__(self):
        return f"Return {self.qty} of {self.sale_item}"


class PurchaseReturn(models.Model):
    purchase_ref = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)



class BadStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bad_stocks')
    qty = models.PositiveIntegerField()
    reason = models.TextField()
    date = models.DateField(auto_now_add=False)

    def __str__(self):
        return f"Bad Stock {self.qty} of {self.product.name}"
