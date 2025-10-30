# accounts/models.py
from django.db import models
from django.db.models import Q
from decimal import Decimal
from core.models import Company
from django.conf import settings

class Account(models.Model):
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
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=150)
    ac_type = models.CharField(max_length=30, choices=AC_TYPE_CHOICES, default=TYPE_OTHER)
    number = models.CharField(max_length=64, blank=True, null=True)
    bank_name = models.CharField(max_length=150, blank=True, null=True)
    branch = models.CharField(max_length=150, blank=True, null=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-id']
        constraints = [
            # Unique constraint for Bank and Mobile banking accounts
            models.UniqueConstraint(
                fields=['company', 'ac_type', 'number'], 
                name='unique_company_ac_type_number',
                condition=Q(ac_type__in=['Bank', 'Mobile banking']) & Q(number__isnull=False)
            ),
            # Only one Cash account per company
            models.UniqueConstraint(
                fields=['company', 'ac_type'],
                name='unique_company_cash_account',
                condition=Q(ac_type='Cash')
            ),
            # Only one Other account per company
            models.UniqueConstraint(
                fields=['company', 'ac_type'],
                name='unique_company_other_account',
                condition=Q(ac_type='Other')
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.ac_type})"

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # For Cash and Other accounts, ensure number is None
        if self.ac_type in [self.TYPE_CASH, self.TYPE_OTHER]:
            self.number = None
            self.bank_name = None
            self.branch = None
            
        if is_new and (self.balance is None or self.balance == 0):
            self.balance = self.opening_balance
        super().save(*args, **kwargs)

    def clean(self):
        """
        Additional validation
        """
        from django.core.exceptions import ValidationError
        
        # Check if Cash account already exists
        if self.ac_type == self.TYPE_CASH and self.pk is None:
            if Account.objects.filter(company=self.company, ac_type=self.TYPE_CASH).exists():
                raise ValidationError("A Cash account already exists for this company.")
                
        # Check if Other account already exists
        if self.ac_type == self.TYPE_OTHER and self.pk is None:
            if Account.objects.filter(company=self.company, ac_type=self.TYPE_OTHER).exists():
                raise ValidationError("An Other account already exists for this company.")