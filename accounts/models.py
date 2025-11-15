# accounts/models.py
from django.db import models
from django.db.models import Q, Max
from decimal import Decimal
from core.models import Company
from django.conf import settings
from django.utils import timezone   
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import random
import string

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
    ac_no = models.CharField(max_length=20, null=True, blank=True)
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
            models.UniqueConstraint(
                fields=['company', 'ac_type', 'number'], 
                name='unique_company_ac_type_number',
                condition=Q(ac_type__in=['Bank', 'Mobile banking']) & Q(number__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['company', 'ac_type'],
                name='unique_company_cash_account',
                condition=Q(ac_type='Cash')
            ),
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

    def create_opening_balance_transaction(self, user):
        """
        Create an opening balance transaction for this account
        """
        if self.opening_balance and self.opening_balance > 0:
            try:
                from transactions.models import Transaction
                
                # Generate transaction number
                last_transaction = Transaction.objects.filter(
                    company=self.company
                ).order_by('-id').first()
                
                transaction_no = "TXN-1001"
                if last_transaction and last_transaction.transaction_no:
                    try:
                        last_number = int(last_transaction.transaction_no.split('-')[-1])
                        new_number = last_number + 1
                        transaction_no = f"TXN-{new_number}"
                    except (ValueError, IndexError):
                        transaction_no = f"TXN-{1001 + (last_transaction.id if last_transaction else 0)}"
                else:
                    transaction_no = "TXN-1001"

                # Create opening balance transaction
                transaction = Transaction.objects.create(
                    company=self.company,
                    transaction_no=transaction_no,
                    account=self,
                    transaction_type='credit',  # Opening balance increases account balance
                    amount=self.opening_balance,
                    description=f"Opening balance for {self.name}",
                    transaction_date=timezone.now().date(),
                    status='completed',
                    created_by=user,
                    is_opening_balance=True
                )
                
                return transaction
            except Exception as e:
                print(f"Error creating opening balance transaction: {e}")
                return None
        return None

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        creating_opening_balance = is_new and self.opening_balance and self.opening_balance > 0
        
        if self.ac_type in [self.TYPE_CASH, self.TYPE_OTHER]:
            self.number = None
            self.bank_name = None
            self.branch = None
            
        if is_new and (self.balance is None or self.balance == 0):
            self.balance = self.opening_balance
        
        # Generate company-specific AC_NO
        if is_new and not self.ac_no:
            # Get the last AC_NO for this company and increment
            last_account = Account.objects.filter(
                company=self.company, 
                ac_no__isnull=False,
                ac_no__startswith='ACC-'
            ).order_by('-ac_no').first()
            
            if last_account and last_account.ac_no:
                try:
                    # Extract the number from AC_NO (e.g., "ACC-1005" -> 1005)
                    last_number = int(last_account.ac_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, start from 1001
                    new_number = 1001
            else:
                # First account for this company
                new_number = 1001
                
            self.ac_no = f"ACC-{new_number}"
        
        # Save the account first
        super().save(*args, **kwargs)
        
        # Create opening balance transaction after saving
        if creating_opening_balance and hasattr(self, '_creating_user'):
            self.create_opening_balance_transaction(self._creating_user)

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.ac_type == self.TYPE_CASH and self.pk is None:
            if Account.objects.filter(company=self.company, ac_type=self.TYPE_CASH).exists():
                raise ValidationError("A Cash account already exists for this company.")
                
        if self.ac_type == self.TYPE_OTHER and self.pk is None:
            if Account.objects.filter(company=self.company, ac_type=self.TYPE_OTHER).exists():
                raise ValidationError("An Other account already exists for this company.")