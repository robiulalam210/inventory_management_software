from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Company
from accounts.models import Account

class ExpenseHead(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name


class ExpenseSubHead(models.Model):
    name = models.CharField(max_length=255)
    head = models.ForeignKey(ExpenseHead, related_name='subheads', on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.head.name} - {self.name}"




class Expense(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    head = models.ForeignKey(ExpenseHead, on_delete=models.CASCADE)
    subhead = models.ForeignKey(ExpenseSubHead, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='expense')
    expense_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.description} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    def generate_invoice_number(self):
        """
        Generate simple invoice number: EXP-1001, EXP-1002, etc.
        """
        # Get the last invoice number
        last_invoice = Expense.objects.filter(
            invoice_number__startswith='EXP-'
        ).order_by('-invoice_number').first()
        
        if last_invoice and last_invoice.invoice_number:
            try:
                # Extract the number part after "EXP-"
                last_number = int(last_invoice.invoice_number.split('-')[1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                # If no valid number found, start from 1001
                next_number = 1001
        else:
            # Start from EXP-1001
            next_number = 1001
        
        return f"EXP-{next_number}"
