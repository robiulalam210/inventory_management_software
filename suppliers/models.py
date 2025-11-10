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

    supplier_no = models.CharField(max_length=50,  blank=True, null=True)
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
        """Update purchase statistics for this supplier - FIXED VERSION"""
        from purchases.models import Purchase
        from decimal import Decimal
        
        try:
            # Get the supplier ID
            supplier_id = self.id
            
            # Use direct SQL to avoid any ORM issues
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(grand_total), 0) as total_purchases,
                        COALESCE(SUM(paid_amount), 0) as total_paid,
                        COUNT(*) as purchase_count
                    FROM purchases_purchase 
                    WHERE supplier_id = %s
                """, [supplier_id])
                
                result = cursor.fetchone()
                total_purchases = result[0] if result[0] else Decimal('0.00')
                total_paid = result[1] if result[1] else Decimal('0.00')
                purchase_count = result[2] if result[2] else 0
            
            total_due = total_purchases - total_paid
            
            # Update using direct SQL
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE suppliers_supplier 
                    SET total_purchases = %s,
                        total_paid = %s, 
                        total_due = %s,
                        purchase_count = %s
                    WHERE id = %s
                """, [total_purchases, total_paid, total_due, purchase_count, supplier_id])
            
            # Refresh this instance
            self.refresh_from_db()
            
            print(f"✅ Supplier {self.name} updated: Due = {self.total_due}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating supplier {self.name}: {e}")
            return False
    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"