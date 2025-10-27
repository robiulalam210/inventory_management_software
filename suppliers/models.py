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

    def __str__(self):
        return f"{self.supplier_no} - {self.name}" if self.supplier_no else self.name

    def save(self, *args, **kwargs):
        if not self.supplier_no:
            last_supplier = Supplier.objects.filter(company=self.company).order_by('-id').first()
            if last_supplier and last_supplier.supplier_no:
                try:
                    last_number = int(last_supplier.supplier_no.split('-')[-1])
                    self.supplier_no = f"SUP-{last_number + 1:04d}"
                except (ValueError, IndexError):
                    self.supplier_no = f"SUP-1001"
            else:
                self.supplier_no = f"SUP-1001"
        super().save(*args, **kwargs)

    def update_purchase_totals(self):
        from purchases.models import Purchase
        from decimal import Decimal
        from django.db import transaction
        
        try:
            purchase_stats = Purchase.objects.filter(
                supplier_id=self.id
            ).aggregate(
                total_purchases=Coalesce(Sum('grand_total'), Decimal('0.00')),
                total_paid=Coalesce(Sum('paid_amount'), Decimal('0.00')),
                purchase_count=Count('id')
            )
            
            with transaction.atomic():
                Supplier.objects.filter(pk=self.pk).update(
                    total_purchases=purchase_stats['total_purchases'],
                    total_paid=purchase_stats['total_paid'],
                    total_due=purchase_stats['total_purchases'] - purchase_stats['total_paid'],
                    purchase_count=purchase_stats['purchase_count']
                )
            
            return True
                
        except Exception as e:
            logger.error(f"Error updating supplier totals: {str(e)}")
            return False

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"