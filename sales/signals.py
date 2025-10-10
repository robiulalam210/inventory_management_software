# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SaleItem, Product

@receiver(post_save, sender=SaleItem)
def decrease_product_stock(sender, instance, **kwargs):
    product = instance.product
    product.stock_qty -= instance.qty  # stock -> stock_qty
    product.save()
