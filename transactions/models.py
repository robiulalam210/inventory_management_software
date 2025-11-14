# transactions/models.py

from django.db import models, transaction
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

    # Basic Info
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    transaction_no = models.CharField(max_length=50, unique=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    # Account
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')

    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    cheque_no = models.CharField(max_length=100, blank=True, null=True)
    reference_no = models.CharField(max_length=100, blank=True, null=True)

    # Dates
    transaction_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Flags
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')

    # Links
    money_receipt = models.ForeignKey(
        'money_receipts.MoneyReceipt', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    expense = models.ForeignKey('expenses.Expense', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    supplier_payment = models.ForeignKey('supplier_payment.SupplierPayment', null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')

    # Extra
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

    # ------------------------------------------------------------------------------
    # SAVE WITH FULL ATOMIC SAFETY
    # ------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Generate code
        if is_new and not self.transaction_no:
            self.transaction_no = self.generate_transaction_no()

        # Validate amount
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be greater than 0")

        # FULL ATOMIC BLOCK
        with transaction.atomic():
            super().save(*args, **kwargs)

            # Update balance ONLY for NEW + completed
            if is_new and self.status == 'completed':
                self.apply_balance_effect()

    # ------------------------------------------------------------------------------
    # UPDATE ACCOUNT BALANCE
    # ------------------------------------------------------------------------------
    def apply_balance_effect(self):
        account = self.account

        if self.transaction_type == 'debit':
            if self.amount > account.balance:
                raise ValidationError("Insufficient balance for debit transaction")
            account.balance -= self.amount

        elif self.transaction_type == 'credit':
            account.balance += self.amount

        account.save(update_fields=['balance'])

    # ------------------------------------------------------------------------------
    # UNIQUE TRANSACTION NO
    # ------------------------------------------------------------------------------
    def generate_transaction_no(self):
        date = timezone.now().strftime('%Y%m%d')
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        base = f"TXN-{date}-{random_part}"
        tx_no = base
        count = 1

        while Transaction.objects.filter(transaction_no=tx_no).exists():
            tx_no = f"{base}-{count}"
            count += 1

        return tx_no

    # ------------------------------------------------------------------------------
    # REVERSE TRANSACTION (Atomic + Safe)
    # ------------------------------------------------------------------------------
    def reverse_transaction(self):
        if self.status != 'completed':
            raise ValidationError("Only completed transactions can be reversed")

        with transaction.atomic():

            reverse_type = 'credit' if self.transaction_type == 'debit' else 'debit'

            reversal = Transaction.objects.create(
                company=self.company,
                transaction_type=reverse_type,
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=f"Reversal of {self.transaction_no}",
                created_by=self.created_by,
                status='completed'
            )

            self.status = 'cancelled'
            self.save(update_fields=['status'])

            return reversal

    # ------------------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------------------
    def clean(self):
        if self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")

        if self.transaction_type == 'debit' and self.status == 'completed':
            if self.amount > self.account.balance:
                raise ValidationError("Insufficient balance for debit transaction")

    @property
    def is_debit(self): return self.transaction_type == 'debit'

    @property
    def is_credit(self): return self.transaction_type == 'credit'

    # ------------------------------------------------------------------------------
    # HELPER METHOD FOR CREATING TRANSACTIONS
    # ------------------------------------------------------------------------------
    @classmethod
    def create_transaction(cls, company, transaction_type, amount, account,
                           payment_method='cash', description='', created_by=None,
                           sale=None, money_receipt=None, expense=None,
                           purchase=None, supplier_payment=None):

        with transaction.atomic():
            trx = cls(
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
                supplier_payment=supplier_payment,
                status='completed'
            )
            trx.save()

        return trx
