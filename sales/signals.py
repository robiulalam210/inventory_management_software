from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Sale, SaleItem


from django.db.models.signals import post_save, pre_save
from .models import Sale
import logging

# sales/signals.py
from django.db import transaction as db_transaction
logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=SaleItem)
def update_sale_totals(sender, instance, **kwargs):
    sale = instance.sale
    total = sum(item.subtotal() for item in sale.items.all())
    sale.gross_total = total
    # Net total = gross_total - overall_discount + overall_service_charge + overall_vat_amount
    sale.net_total = total - sale.overall_discount + sale.overall_service_charge + sale.overall_vat_amount
    sale.save()




# In sales/models.py or sales/signals.py
def create_sale_transaction(sender, instance, created, **kwargs):
    """Let MoneyReceipt handle all payment transactions"""
    # Only create money receipt, not transaction
    if (hasattr(instance, '_old_paid_amount') and 
        instance.paid_amount > instance._old_paid_amount and
        instance.with_money_receipt == 'Yes'):
        
        # Money receipt will create the transaction
        instance.create_money_receipt()


@receiver(pre_save, sender=Sale)
def track_sale_changes(sender, instance, **kwargs):
    """Track changes in sale for transaction creation"""
    if instance.pk:
        try:
            old_instance = Sale.objects.get(pk=instance.pk)
            instance._old_paid_amount = old_instance.paid_amount
            instance._old_account = old_instance.account
        except Sale.DoesNotExist:
            instance._old_paid_amount = 0
            instance._old_account = None

@receiver(post_save, sender=Sale)
def create_sale_transaction(sender, instance, created, **kwargs):
    """Create transaction when sale payment is made"""
    try:
        # Only create transaction if payment was increased and account exists
        if (hasattr(instance, '_old_paid_amount') and 
            instance.paid_amount > instance._old_paid_amount and
            instance.account and instance.paid_amount > 0):
            
            payment_amount = instance.paid_amount - instance._old_paid_amount
            
            # Import here to avoid circular imports
            from transactions.services import TransactionService
            
            TransactionService.create_sale_transaction(
                sale=instance,
                account=instance.account,
                payment_method=instance.payment_method or 'cash',
                amount=payment_amount,
                created_by=instance.created_by
            )
            
            logger.info(f"Transaction created for sale {instance.invoice_no}")
            
    except ImportError as e:
        logger.error(f"Failed to import TransactionService: {e}")
    except Exception as e:
        logger.error(f"Error creating transaction for sale {instance.invoice_no}: {str(e)}")