# customers/models.py
from django.db import models
from core.models import Company
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

class Customer(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")
    
    # NEW: Advance payment tracking
    advance_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    client_no = models.CharField(max_length=20, blank=True, null=True)

    def save(self, *args, **kwargs):
        """Custom save method to handle client number generation"""
        is_new = self.pk is None
        
        # Generate client number for new customers if not provided
        if is_new and not self.client_no:
            existing_count = Customer.objects.filter(
                company=self.company,
                client_no__isnull=False
            ).count()
            new_number = 1001 + existing_count
            self.client_no = f"CU-{new_number}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

    def add_advance_direct(self, amount, created_by=None):
        """Add advance payment directly to customer balance WITHOUT money receipt"""
        if amount <= 0:
            raise ValidationError("Advance amount must be greater than 0")
        
        # Directly update advance balance
        self.advance_balance += amount
        self.save(update_fields=['advance_balance'])
        
        return self.advance_balance


    def use_advance_payment(self, amount, sale=None):
        """Use advance balance for a payment"""
        if amount > self.advance_balance:
            raise ValidationError(f"Insufficient advance balance. Available: {self.advance_balance}")
        
        self.advance_balance -= amount
        self.save(update_fields=['advance_balance'])
        
        return self.advance_balance
    def get_payment_summary(self):
            """Get comprehensive payment summary including advance"""
            from sales.models import Sale
            from django.db.models import Sum
            
            # Get all sales for this customer
            sales = Sale.objects.filter(customer=self, company=self.company)
            
            # Calculate totals
            total_sales = sales.count()
            total_grand_total = sales.aggregate(total=Sum('grand_total'))['total'] or 0
            total_paid = sales.aggregate(total=Sum('paid_amount'))['total'] or 0
            total_due = sales.aggregate(total=Sum('due_amount'))['total'] or 0
            
            # Calculate advance balance (overpayments)
            advance_balance = max(0, total_paid - total_grand_total)
            
            # Adjust due amount (should not be negative)
            adjusted_due = max(0, total_due)
            
            return {
                'customer': self.name,
                'total_sales': total_sales,
                'total_grand_total': float(total_grand_total),
                'total_paid': float(total_paid),
                'total_due': float(adjusted_due),
                'advance_balance': float(advance_balance),
                'amount_type': 'Advance' if advance_balance > 0 else ('Paid' if total_due == 0 else 'Due')
            }
    def get_advance_summary(self):
        """Get advance payment summary"""
        from money_receipts.models import MoneyReceipt
        from django.db.models import Sum
        
        advance_receipts = MoneyReceipt.objects.filter(
            customer=self,
            is_advance_payment=True,
            payment_status='completed'
        )
        
        total_advance = advance_receipts.aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'customer': self.name,
            'current_balance': float(self.advance_balance),
            'total_advance_received': float(total_advance),
            'advance_receipts_count': advance_receipts.count()
        }