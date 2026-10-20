# suppliers/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from purchases.models import Purchase
import logging
import logging as _logging
_dbg = _logging.getLogger(__name__).debug  # আগের print — production log এ যায় না


logger = logging.getLogger(__name__)

@receiver(post_save, sender=Purchase)
def update_supplier_on_purchase_save(sender, instance, **kwargs):
    """Update supplier totals when purchase is saved"""
    try:
        if instance.supplier:
            _dbg(f"🔄 Updating supplier totals for {instance.supplier.name}")
            instance.supplier.update_purchase_totals()
    except Exception as e:
        logger.error(f"Error updating supplier on purchase save: {str(e)}")

@receiver(post_delete, sender=Purchase)
def update_supplier_on_purchase_delete(sender, instance, **kwargs):
    """Update supplier totals when purchase is deleted"""
    try:
        if instance.supplier:
            _dbg(f"🔄 Updating supplier totals after delete for {instance.supplier.name}")
            instance.supplier.update_purchase_totals()
    except Exception as e:
        logger.error(f"Error updating supplier on purchase delete: {str(e)}")