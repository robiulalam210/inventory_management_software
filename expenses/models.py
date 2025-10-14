from django.db import models

from core.models import Company
from accounts.models import Account

class ExpenseHead(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name


class ExpenseSubHead(models.Model):
    name = models.CharField(max_length=255)
    head = models.ForeignKey(ExpenseHead, related_name='subheads', on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.head.name} - {self.name}"




class Expense(models.Model):
  

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    head = models.ForeignKey(ExpenseHead, on_delete=models.CASCADE)
    subhead = models.ForeignKey(ExpenseSubHead, on_delete=models.CASCADE, null=True, blank=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100, blank=True, null=True)  # or use choices if needed
    account = models.ForeignKey( Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='expense')
    expense_date = models.DateField()
    note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"
