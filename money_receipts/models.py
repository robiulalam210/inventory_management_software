from django.db import models
from core.models import Company
from customers.models import Customer
from accounts.models import Account
from sales.models import Sale       
from django.contrib.auth import get_user_model

User = get_user_model()
class MoneyReceipt(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('overall', 'Overall Payment'),
        ('specific', 'Specific Invoice Payment'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mr_no = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Payment type fields
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='overall')
    specific_invoice = models.BooleanField(default=False)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100)
    payment_date = models.DateTimeField()
    remark = models.TextField(null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_status = models.CharField(max_length=20, null=True, blank=True)
    cheque_id = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mr_no} - {self.customer.name}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Generate MR number
        if is_new and not self.mr_no:
            try:
                last_receipt = MoneyReceipt.objects.filter(company=self.company).order_by("-id").first()
                new_id = (last_receipt.id + 1) if last_receipt else 1
                self.mr_no = f"MR-{1000 + new_id}"
            except:
                self.mr_no = f"MR-{1000 + 1}"
        
        # Set payment type based on sale existence
        if self.sale:
            self.payment_type = 'specific'
            self.specific_invoice = True
        else:
            self.payment_type = 'overall'
            self.specific_invoice = False
        
        super().save(*args, **kwargs)
        
        # Process payment after save
        if is_new:
            self.process_payment()

    def process_payment(self):
        """
        Process payment based on payment type
        """
        try:
            if self.payment_type == 'specific' and self.sale:
                self._process_specific_invoice_payment()
            else:
                self._process_overall_payment()
        except Exception as e:
            print(f"Payment processing error: {e}")
            # You might want to log this or handle it differently

    def _process_specific_invoice_payment(self):
        """
        Process specific invoice payment
        """
        if not self.sale:
            return False

        # Check due amount
        if self.amount > self.sale.due_amount:
            raise ValueError(f"Payment amount ({self.amount}) cannot be greater than due amount ({self.sale.due_amount})")

        # Update sale
        self.sale.paid_amount += self.amount
        self.sale.due_amount = max(0, self.sale.due_amount - self.amount)
        
        # Update payment status
        if self.sale.due_amount == 0:
            self.sale.payment_status = 'paid'
        elif self.sale.paid_amount > 0:
            self.sale.payment_status = 'partial'
            
        self.sale.save()
        return True

    def _process_overall_payment(self):
        """
        Process overall payment (distribute to due sales)
        """
        # Get all due sales for customer
        due_sales = Sale.objects.filter(
            customer=self.customer,
            company=self.company,
            due_amount__gt=0
        ).order_by('sale_date')
        
        remaining_amount = self.amount
        
        for sale in due_sales:
            if remaining_amount <= 0:
                break
                
            # Calculate applicable amount for this sale
            applicable_amount = min(remaining_amount, sale.due_amount)
            
            # Update sale
            sale.paid_amount += applicable_amount
            sale.due_amount -= applicable_amount
            
            # Update payment status
            if sale.due_amount == 0:
                sale.payment_status = 'paid'
            elif sale.paid_amount > 0:
                sale.payment_status = 'partial'
                
            sale.save()
            remaining_amount -= applicable_amount
            
        return True

    def get_payment_summary(self):
        """
        Get payment summary based on type
        """
        if self.payment_type == 'specific' and self.sale:
            return self._get_specific_invoice_summary()
        else:
            return self._get_overall_payment_summary()

    def _get_specific_invoice_summary(self):
        """
        Get specific invoice payment summary
        """
        previous_paid = self.sale.paid_amount - self.amount if self.sale else 0
        previous_due = (self.sale.due_amount + self.amount) if self.sale else 0
        
        summary = {
            'payment_type': 'specific_invoice',
            'invoice_no': self.sale.invoice_no if self.sale else 'N/A',
            'before_payment': {
                'invoice_total': float(self.sale.grand_total) if self.sale else 0,
                'previous_paid': float(previous_paid),
                'previous_due': float(previous_due),
            },
            'after_payment': {
                'current_paid': float(self.sale.paid_amount) if self.sale else 0,
                'current_due': float(self.sale.due_amount) if self.sale else 0,
                'payment_applied': float(self.amount)
            },
            'status': 'completed' if self.sale and self.sale.due_amount == 0 else 'partial'
        }
        return summary

    def _get_overall_payment_summary(self):
        """
        Get overall payment summary
        """
        from django.db.models import Sum
        
        # Customer total due before payment
        total_due_before = Sale.objects.filter(
            customer=self.customer,
            company=self.company,
            due_amount__gt=0
        ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0
        
        total_due_after = max(total_due_before - self.amount, 0)
        previous_total_paid = self.get_customer_total_paid() - self.amount
        
        summary = {
            'payment_type': 'overall',
            'before_payment': {
                'total_due': float(total_due_before),
                'total_paid': float(previous_total_paid),
            },
            'after_payment': {
                'total_due': float(total_due_after),
                'payment_applied': float(self.amount),
                'remaining_due': float(total_due_after)
            },
            'affected_invoices': self.get_affected_invoices(),
            'status': 'completed' if total_due_after == 0 else 'partial'
        }
        return summary

    def get_customer_total_paid(self):
        """Get customer total paid amount"""
        from django.db.models import Sum
        total_paid = Sale.objects.filter(
            customer=self.customer,
            company=self.company
        ).aggregate(total_paid=Sum('paid_amount'))['total_paid'] or 0
        return total_paid

    def get_affected_invoices(self):
        """Get invoices affected by this payment"""
        if self.payment_type == 'specific' and self.sale:
            return [{
                'invoice_no': self.sale.invoice_no,
                'amount_applied': float(self.amount)
            }]
        else:
            # For overall payment - get affected invoices
            affected = []
            remaining = self.amount
            
            due_sales = Sale.objects.filter(
                customer=self.customer, 
                company=self.company,
                due_amount__gt=0
            ).order_by('sale_date')
            
            for sale in due_sales:
                if remaining <= 0:
                    break
                    
                applied = min(remaining, sale.due_amount)
                affected.append({
                    'invoice_no': sale.invoice_no,
                    'amount_applied': float(applied),
                    'sale_id': sale.id
                })
                remaining -= applied
                
            return affected

    class Meta:
        ordering = ['-created_at']