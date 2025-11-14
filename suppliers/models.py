# suppliers/models.py
from django.db import models
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from core.models import Company
from django.conf import settings
from django.core.exceptions import ValidationError
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

    # Purchase statistics
    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    purchase_count = models.IntegerField(default=0)
    
    # Advance balance
    advance_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['company', 'supplier_no']

    def __str__(self):
        return f"{self.supplier_no} - {self.name}" if self.supplier_no else self.name

    def save(self, *args, **kwargs):
        if not self.supplier_no:
            self.supplier_no = self.generate_supplier_no()
        super().save(*args, **kwargs)

    def generate_supplier_no(self):
        """Generate unique supplier number"""
        try:
            last_supplier = Supplier.objects.filter(
                company=self.company
            ).order_by('-supplier_no').first()
            
            if last_supplier and last_supplier.supplier_no:
                try:
                    last_number = int(last_supplier.supplier_no.split('-')[1])
                    new_number = last_number + 1
                except:
                    new_number = 1001
            else:
                new_number = 1001
                
            return f"SUP-{new_number}"
        except:
            return f"SUP-1001"

    def update_purchase_totals(self):
        """Update purchase statistics - FIXED VERSION"""
        try:
            from purchases.models import Purchase
            
            aggregates = Purchase.objects.filter(
                supplier=self,
                company=self.company
            ).aggregate(
                total_purchases=Coalesce(Sum('grand_total'), Decimal('0.00')),
                total_paid=Coalesce(Sum('paid_amount'), Decimal('0.00')),
                purchase_count=Coalesce(Count('id'), 0)
            )
            
            # Convert None to 0 and ensure Decimal values
            self.total_purchases = aggregates['total_purchases'] or Decimal('0.00')
            self.total_paid = aggregates['total_paid'] or Decimal('0.00')
            self.purchase_count = aggregates['purchase_count'] or 0
            self.total_due = max(Decimal('0.00'), self.total_purchases - self.total_paid)
            
            # Save with all fields to ensure consistency
            self.save(update_fields=[
                'total_purchases', 'total_paid', 'total_due', 'purchase_count', 'updated_at'
            ])
            
            logger.info(f"✅ Supplier totals updated: {self.name} - "
                    f"Purchases: {self.total_purchases}, "
                    f"Paid: {self.total_paid}, "
                    f"Due: {self.total_due}, "
                    f"Advance: {self.advance_balance}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating supplier totals for {self.name}: {e}")
            return False
        
    @classmethod
    def recalculate_all_supplier_totals(cls, company=None):
        """Recalculate totals for all suppliers - useful for fixing data"""
        try:
            suppliers = cls.objects.all()
            if company:
                suppliers = suppliers.filter(company=company)
            
            for supplier in suppliers:
                logger.info(f"Recalculating totals for supplier: {supplier.name}")
                supplier.update_purchase_totals()
                
            logger.info(f"✅ Recalculated totals for {suppliers.count()} suppliers")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error recalculating supplier totals: {e}")
            return False

    @property
    def payment_status(self):
        if self.total_due <= 0 and self.advance_balance > 0:
            return "Advance"
        elif self.total_due == 0:
            return "Paid"
        elif self.total_due == self.total_purchases:
            return "Unpaid"
        else:
            return "Partial"

    def get_payment_summary(self):
        return {
            'supplier': self.name,
            'total_purchases': float(self.total_purchases),
            'total_paid': float(self.total_paid),
            'total_due': float(self.total_due),
            'advance_balance': float(self.advance_balance),
            'payment_status': self.payment_status,
            'purchase_count': self.purchase_count
        }