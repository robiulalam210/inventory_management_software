from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Sale, SaleItem

@receiver([post_save, post_delete], sender=SaleItem)
def update_sale_totals(sender, instance, **kwargs):
    sale = instance.sale
    total = sum(item.subtotal() for item in sale.items.all())
    sale.gross_total = total
    # Net total = gross_total - overall_discount + overall_service_charge + overall_vat_amount
    sale.net_total = total - sale.overall_discount + sale.overall_service_charge + sale.overall_vat_amount
    sale.save()
