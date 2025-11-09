# suppliers/models.py
from django.db import models
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from core.models import Company
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    supplier_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    purchase_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['supplier_no']),
            models.Index(fields=['name']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return f"{self.supplier_no} - {self.name}" if self.supplier_no else self.name

    def save(self, *args, **kwargs):
        if not self.supplier_no:
            self.supplier_no = self.generate_supplier_no()
        super().save(*args, **kwargs)

    def generate_supplier_no(self):
        """Generate unique supplier number for the company"""
        try:
            last_supplier = Supplier.objects.filter(
                company=self.company
            ).order_by('-id').first()
            
            if last_supplier and last_supplier.supplier_no:
                try:
                    last_number = int(last_supplier.supplier_no.split('-')[-1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1001
            else:
                new_number = 1001
                
            return f"SUP-{new_number:04d}"
        except Exception as e:
            logger.error(f"Error generating supplier number: {str(e)}")
            return f"SUP-1001"

    def update_purchase_totals(self):
        """Update purchase statistics for this supplier"""
        from purchases.models import Purchase
        from decimal import Decimal
        from django.db import transaction
        
        try:
            purchase_stats = Purchase.objects.filter(
                supplier=self
            ).aggregate(
                total_purchases=Coalesce(Sum('grand_total'), Decimal('0.00')),
                total_paid=Coalesce(Sum('paid_amount'), Decimal('0.00')),
                purchase_count=Count('id')
            )
            
            with transaction.atomic():
                # Refresh the instance to avoid race conditions
                supplier = Supplier.objects.select_for_update().get(pk=self.pk)
                supplier.total_purchases = purchase_stats['total_purchases']
                supplier.total_paid = purchase_stats['total_paid']
                supplier.total_due = purchase_stats['total_purchases'] - purchase_stats['total_paid']
                supplier.purchase_count = purchase_stats['purchase_count']
                supplier.save(update_fields=[
                    'total_purchases', 'total_paid', 'total_due', 'purchase_count'
                ])
            
            logger.info(f"Updated purchase totals for supplier {self.supplier_no}")
            return True
                
        except Exception as e:
            logger.error(f"Error updating supplier totals for {self.supplier_no}: {str(e)}")
            return False

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"