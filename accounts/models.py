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

    ACCOUNT_TYPE_CHOICES = [
        (TYPE_BANK, 'Bank'),
        (TYPE_MOBILE, 'Mobile banking'),
        (TYPE_CASH, 'Cash'),
        (TYPE_OTHER, 'Other'),
    ]

    ac_no = models.CharField(max_length=20, null=True, blank=True, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=150)
    ac_type = models.CharField(max_length=30, choices=ACCOUNT_TYPE_CHOICES, default=TYPE_OTHER)
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
            # Bank and Mobile banking must have unique numbers
            models.UniqueConstraint(
                fields=['company', 'ac_type', 'number'], 
                name='unique_company_ac_type_number',
                condition=Q(ac_type__in=['Bank', 'Mobile banking']) & Q(number__isnull=False)
            ),
            # Cash and Other accounts can have multiple entries, even without numbers
        ]
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return f"{self.name} ({self.ac_type}) - {self.company}"

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
                
                # Generate company-specific transaction number
                company_prefix = self.company.name[:3].upper() if self.company else "COM"
                timestamp = int(timezone.now().timestamp())
                transaction_no = f"{company_prefix}-OB-{timestamp}"
                
                # Ensure uniqueness
                counter = 1
                base_no = transaction_no
                while Transaction.objects.filter(transaction_no=transaction_no).exists():
                    transaction_no = f"{base_no}-{counter}"
                    counter += 1
                    if counter > 100:
                        # Ultimate fallback
                        transaction_no = f"{company_prefix}-OB-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                        break

                # Create opening balance transaction WITH special flag
                transaction = Transaction.objects.create(
                    company=self.company,
                    transaction_no=transaction_no,
                    account=self,
                    transaction_type='credit',
                    amount=self.opening_balance,
                    description=f"Opening balance for {self.name}",
                    transaction_date=timezone.now().date(),
                    status='completed',
                    created_by=user,
                    is_opening_balance=True
                )
                
                return transaction
            except Exception as e:
                return None
        return None

    def save(self, *args, **kwargs):
        # Extract user from kwargs if provided
        user = kwargs.pop('creating_user', None)
        
        is_new = self.pk is None
        creating_opening_balance = is_new and self.opening_balance and self.opening_balance > 0
        
        # Clean up fields based on account type
        if self.ac_type in [self.TYPE_CASH, self.TYPE_OTHER]:
            self.bank_name = None
            self.branch = None
            # For Cash accounts without number, generate a default name-based number
            if self.ac_type == self.TYPE_CASH and not self.number:
                self.number = f"CASH-{self.name.upper().replace(' ', '-')}"
        
        # Set initial balance to opening_balance for new accounts
        if is_new:
            self.balance = self.opening_balance
        
        # Generate company-specific AC_NO
        if is_new and not self.ac_no:
            company_prefix = self.company.name[:3].upper() if self.company else "COM"
            last_account = Account.objects.filter(
                company=self.company, 
                ac_no__isnull=False,
                ac_no__startswith=f'{company_prefix}-ACC-'
            ).order_by('-ac_no').first()
            
            if last_account and last_account.ac_no:
                try:
                    last_number = int(last_account.ac_no.split('-')[-1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1001
            else:
                new_number = 1001
                
            self.ac_no = f"{company_prefix}-ACC-{new_number}"
        
        # Save the account first
        super().save(*args, **kwargs)
        
        # Create opening balance transaction after saving (for record keeping only)
        if creating_opening_balance and user:
            self.create_opening_balance_transaction(user)
            
    def clean(self):
        """Validate account data"""
        from django.core.exceptions import ValidationError
        
        # Bank and Mobile banking must have numbers
        if self.ac_type in [self.TYPE_BANK, self.TYPE_MOBILE]:
            if not self.number or self.number.strip() == '':
                raise ValidationError({
                    'number': f"{self.ac_type} accounts must have an account number."
                })
        
        # Check for duplicates (only for Bank and Mobile banking with numbers)
        if self.ac_type in [self.TYPE_BANK, self.TYPE_MOBILE] and self.number:
            existing_account = Account.objects.filter(
                company=self.company,
                ac_type=self.ac_type,
                number=self.number
            ).exclude(pk=self.pk).first()
            
            if existing_account:
                raise ValidationError(
                    f"A {self.ac_type} account with number '{self.number}' already exists."
                )
        
        # Validate opening balance
        if self.opening_balance is None:
            self.opening_balance = Decimal('0.00')