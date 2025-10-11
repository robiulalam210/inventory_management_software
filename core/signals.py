from django.db.models.signals import post_save
from django.dispatch import receiver
from returns.models import SalesReturn, PurchaseReturn, BadStock
from products.models import Product

@receiver(post_save, sender=SalesReturn)
def create_badstock_from_sales_return(sender, instance, created, **kwargs):
    if created and instance.qty > 0:
        if 'bad' in instance.reason.lower() or 'damaged' in instance.reason.lower():
            BadStock.objects.create(
                product=instance.sale_item.product,
                qty=instance.qty,
                reason=f"Sales Return: {instance.reason}",
                date=instance.date
            )
            # stock_qty থেকে কমানো
            product = instance.sale_item.product
            product.stock_qty -= instance.qty
            product.save()


@receiver(post_save, sender=PurchaseReturn)
def create_badstock_from_purchase_return(sender, instance, created, **kwargs):
    if created and instance.quantity > 0:
        BadStock.objects.create(
            product=instance.product_ref,
            qty=instance.quantity,
            reason=f"Purchase Return",
            date=instance.date.date()  # DateField-এ মান দেওয়া
        )
        # stock_qty থেকে কমানো
        product = instance.product_ref
        product.stock_qty -= instance.quantity
        product.save()
