
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SaleItem

@receiver(post_save, sender=SaleItem)
def decrease_product_stock(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        product.stock -= instance.qty
        product.save()
