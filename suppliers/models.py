# suppliers/models.py
from django.db import models
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from core.models import Company
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    supplier_no = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # ✅ ADD THESE FIELDS
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
        try:
            # LAZY IMPORT to avoid circular dependency
            from purchases.models import Purchase
            
            logger.info(f"🔄 Supplier.update_purchase_totals called for: {self.name}")
            
            # Use Django ORM with proper filtering
            aggregates = Purchase.objects.filter(
                supplier=self,
                company=self.company
            ).aggregate(
                total_purchases=Sum('grand_total'),
                total_paid=Sum('paid_amount'),
                purchase_count=Count('id')
            )
            
            # Handle None values
            total_purchases = aggregates['total_purchases'] or Decimal('0.00')
            total_paid = aggregates['total_paid'] or Decimal('0.00')
            purchase_count = aggregates['purchase_count'] or 0
            total_due = total_purchases - total_paid
            
            logger.info(f"📊 Supplier {self.name}: Purchases={total_purchases}, Paid={total_paid}, Due={total_due}, Count={purchase_count}")
            
            # Update fields
            self.total_purchases = total_purchases
            self.total_paid = total_paid
            self.total_due = total_due
            self.purchase_count = purchase_count
            
            # Save without triggering signals
            super(Supplier, self).save(update_fields=[
                'total_purchases', 'total_paid', 'total_due', 'purchase_count'
            ])
            
            logger.info(f"✅ Supplier {self.name} updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating supplier {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"