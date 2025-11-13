# transactions/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.models import Company
from accounts.models import Account
from django.conf import settings
import random
import string

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('mobile', 'Mobile Banking'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Basic Information
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    transaction_no = models.CharField(max_length=50, unique=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    
    # Account Information
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    
    # Payment Information
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    cheque_no = models.CharField(max_length=100, blank=True, null=True)
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    
    # Dates
    transaction_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    money_receipt = models.ForeignKey(
        'money_receipts.MoneyReceipt', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'  # This creates Transaction.objects.filter(money_receipt=...)
    )
    # Relationships - Use string references
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    expense = models.ForeignKey('expenses.Expense', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    supplier_payment = models.ForeignKey('supplier_payment.SupplierPayment', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    # Additional Info
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-transaction_date', '-id']
        indexes = [
            models.Index(fields=['company', 'transaction_date']),
            models.Index(fields=['account', 'transaction_date']),
            models.Index(fields=['transaction_no']),
        ]
    
    def __str__(self):
        return f"{self.transaction_no} - {self.transaction_type} - {self.amount}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Generate transaction number
        if is_new and not self.transaction_no:
            self.transaction_no = self.generate_transaction_no()
        
        # Validate amount
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be greater than 0")
        
        # Save transaction first
        super().save(*args, **kwargs)
        
        # Update account balance only for completed transactions
        if self.status == 'completed' and is_new:
            self.update_account_balance()
    
    def generate_transaction_no(self):
        """Generate unique transaction number: TXN-YYYYMMDD-XXXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        base_no = f"TXN-{date_str}-{random_str}"
        transaction_no = base_no
        
        # Ensure uniqueness
        counter = 1
        while Transaction.objects.filter(transaction_no=transaction_no).exists():
            transaction_no = f"{base_no}-{counter}"
            counter += 1
        
        return transaction_no
    
    def update_account_balance(self):
        """Update account balance based on transaction type"""
        if self.transaction_type == 'debit':
            self.account.balance -= self.amount
        elif self.transaction_type == 'credit':
            self.account.balance += self.amount
        
        self.account.save(update_fields=['balance'])
    
    def reverse_transaction(self):
        """Reverse this transaction and create a reversal transaction"""
        if self.status != 'completed':
            raise ValidationError("Only completed transactions can be reversed")
        
        # Create reversal transaction
        reversal = Transaction(
            company=self.company,
            transaction_type='credit' if self.transaction_type == 'debit' else 'debit',
            amount=self.amount,
            account=self.account,
            payment_method=self.payment_method,
            description=f"Reversal of {self.transaction_no}",
            created_by=self.created_by,
            status='completed'
        )
        reversal.save()
        
        # Mark original as cancelled
        self.status = 'cancelled'
        self.save(update_fields=['status'])
        
        return reversal
    
    def clean(self):
        """Additional validation"""
        if self.transaction_type not in ['debit', 'credit']:
            raise ValidationError("Transaction type must be either debit or credit")
        
        # Ensure account belongs to the same company
        if self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")
        
        # Check for sufficient balance for debit transactions
        if (self.transaction_type == 'debit' and 
            self.status == 'completed' and 
            self.amount > self.account.balance):
            raise ValidationError("Insufficient account balance for debit transaction")

    @property
    def is_debit(self):
        return self.transaction_type == 'debit'
    
    @property
    def is_credit(self):
        return self.transaction_type == 'credit'
    
    @classmethod
    def create_transaction(cls, company, transaction_type, amount, account, 
                         payment_method='cash', description='', created_by=None,
                         sale=None, money_receipt=None, expense=None, 
                         purchase=None, supplier_payment=None):
        """Helper method to create transactions"""
        transaction = cls(
            company=company,
            transaction_type=transaction_type,
            amount=amount,
            account=account,
            payment_method=payment_method,
            description=description,
            created_by=created_by,
            sale=sale,
            money_receipt=money_receipt,
            expense=expense,
            purchase=purchase,
            supplier_payment=supplier_payment
        )
        transaction.save()
        return transaction