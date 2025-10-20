# suppliers/models.py
from django.db import models
from django.db.models import Sum, Count, Value
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from core.models import Company
from django.conf import settings

class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Add these fields for purchase totals
    total_purchases = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    purchase_count = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def update_purchase_totals(self):
        """Update supplier purchase totals - Fixed version"""
        from purchases.models import Purchase
        from decimal import Decimal
        from django.db import transaction
        
        try:
            print(f"🔄 Supplier.update_purchase_totals: Starting for supplier '{self.name}' (ID: {self.id})")
            
            # Get ALL purchases for this supplier using supplier_id (more reliable)
            purchases = Purchase.objects.filter(supplier_id=self.id)
            print(f"   Found {purchases.count()} purchases for supplier ID {self.id}")
            
            # Manual calculation - force float conversion to avoid Decimal issues
            total_purchases = 0.0
            total_paid = 0.0
            
            for i, purchase in enumerate(purchases, 1):
                print(f"   Purchase {i}: ID={purchase.id}, Invoice={purchase.invoice_no}, "
                      f"Grand Total={purchase.grand_total}, Paid={purchase.paid_amount}")
                
                total_purchases += float(purchase.grand_total)
                total_paid += float(purchase.paid_amount)
            
            # Convert back to Decimal
            total_purchases_decimal = Decimal(str(total_purchases))
            total_paid_decimal = Decimal(str(total_paid))
            total_due = total_purchases_decimal - total_paid_decimal
            purchase_count = purchases.count()
            
            print(f"   📊 Final calculation: Purchases=${total_purchases_decimal}, Paid=${total_paid_decimal}, "
                  f"Due=${total_due}, Count={purchase_count}")
            
            # Update supplier fields
            self.total_purchases = total_purchases_decimal
            self.total_paid = total_paid_decimal
            self.total_due = total_due
            self.purchase_count = purchase_count
            
            # Save using direct update
            with transaction.atomic():
                Supplier.objects.filter(pk=self.pk).update(
                    total_purchases=self.total_purchases,
                    total_paid=self.total_paid,
                    total_due=self.total_due,
                    purchase_count=self.purchase_count
                )
            
            print(f"   ✅ Successfully updated supplier '{self.name}'")
            return True
                
        except Exception as e:
            print(f"❌ ERROR updating supplier totals for {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return False