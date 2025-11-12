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

    # ✅ Purchase statistics fields
    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_due = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
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
        # ✅ Add unique constraint for company + supplier_no
        unique_together = ['company', 'supplier_no']

    def __str__(self):
        return f"{self.supplier_no} - {self.name}" if self.supplier_no else self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Generate supplier number only for new instances
        if is_new and not self.supplier_no:
            self.supplier_no = self.generate_supplier_no()
        
        super().save(*args, **kwargs)

    def generate_supplier_no(self):
        """Generate unique supplier number for the company"""
        try:
            # Get the last supplier number for this company
            last_supplier = Supplier.objects.filter(
                company=self.company,
                supplier_no__isnull=False,
                supplier_no__startswith='SUP-'
            ).order_by('-supplier_no').first()
            
            if last_supplier and last_supplier.supplier_no:
                try:
                    # Extract number from "SUP-1001" format
                    last_number = int(last_supplier.supplier_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing suppliers
                    existing_count = Supplier.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First supplier for this company
                new_number = 1001
                
            return f"SUP-{new_number}"
            
        except Exception as e:
            logger.error(f"Error generating supplier number: {str(e)}")
            # Fallback: use count-based numbering
            existing_count = Supplier.objects.filter(company=self.company).count()
            return f"SUP-{1001 + existing_count}"

    def update_purchase_totals(self):
        """Update purchase statistics for this supplier"""
        try:
            # LAZY IMPORT to avoid circular dependency
            from purchases.models import Purchase
            
            logger.info(f"🔄 Supplier.update_purchase_totals called for: {self.name}")
            
            # Use Coalesce to handle None values properly
            aggregates = Purchase.objects.filter(
                supplier=self,
                company=self.company
            ).aggregate(
                total_purchases=Coalesce(Sum('grand_total'), Decimal('0.00')),
                total_paid=Coalesce(Sum('paid_amount'), Decimal('0.00')),
                purchase_count=Coalesce(Count('id'), 0)
            )
            
            total_purchases = aggregates['total_purchases']
            total_paid = aggregates['total_paid']
            purchase_count = aggregates['purchase_count']
            total_due = total_purchases - total_paid
            
            logger.info(f"📊 Supplier {self.name}: Purchases={total_purchases}, Paid={total_paid}, Due={total_due}, Count={purchase_count}")
            
            # Update fields only if they changed
            if (self.total_purchases != total_purchases or 
                self.total_paid != total_paid or 
                self.total_due != total_due or 
                self.purchase_count != purchase_count):
                
                self.total_purchases = total_purchases
                self.total_paid = total_paid
                self.total_due = total_due
                self.purchase_count = purchase_count
                
                # Save without triggering signals
                super(Supplier, self).save(update_fields=[
                    'total_purchases', 'total_paid', 'total_due', 'purchase_count', 'updated_at'
                ])
                
                logger.info(f"✅ Supplier {self.name} totals updated successfully")
            else:
                logger.info(f"ℹ️  Supplier {self.name} totals unchanged, skipping update")
            
            return True
            
        except ImportError:
            logger.warning("Purchase model not available yet (migrations)")
            return False
        except Exception as e:
            logger.error(f"❌ Error updating supplier {self.name}: {str(e)}")
            return False

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

    @property
    def payment_status(self):
        """Get payment status based on due amount"""
        if self.total_due == 0:
            return "Paid"
        elif self.total_due == self.total_purchases:
            return "Unpaid"
        else:
            return "Partial"

    def get_payment_percentage(self):
        """Get percentage of total amount paid"""
        if self.total_purchases == 0:
            return 100
        return round((self.total_paid / self.total_purchases) * 100, 2)