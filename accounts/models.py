from django.db import models
from decimal import Decimal

class Account(models.Model):
    # Type constants
    TYPE_BANK = 'Bank'
    TYPE_MOBILE = 'Mobile banking'
    TYPE_CASH = 'Cash'
    TYPE_OTHER = 'Other'

    AC_TYPE_CHOICES = [
        (TYPE_BANK, 'Bank'),
        (TYPE_MOBILE, 'Mobile banking'),
        (TYPE_CASH, 'Cash'),
        (TYPE_OTHER, 'Other'),
    ]

    name = models.CharField(max_length=150)  # Account name
    ac_type = models.CharField(max_length=30, choices=AC_TYPE_CHOICES, default=TYPE_OTHER)
    number = models.CharField(max_length=64, blank=True, null=True)  # Account number
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    branch = models.CharField(max_length=150, blank=True, null=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} ({self.ac_type})"

    def save(self, *args, **kwargs):
        if self.balance is None:
            self.balance = self.opening_balance
        super().save(*args, **kwargs)
