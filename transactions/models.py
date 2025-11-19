from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.models import Company
from accounts.models import Account
from django.conf import settings
import random
import string
import logging

logger = logging.getLogger(__name__)

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
    is_opening_balance = models.BooleanField(default=False)

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
        'money_receipts.MoneyReceipt', 
        on_delete=models.SET_NULL,
        null=True, blank=True, 
        related_name='transactions'
    )
    sale = models.ForeignKey(
        'sales.Sale', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='transactions'
    )
    expense = models.ForeignKey(
        'expenses.Expense', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='transactions'
    )
    purchase = models.ForeignKey(
        'purchases.Purchase', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='transactions'
    )

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

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Generate transaction number if new
        if is_new and not self.transaction_no:
            self.transaction_no = self._generate_transaction_no()

        # Validate before saving
        self.clean()

        # Save the transaction first
        super().save(*args, **kwargs)

        # DEBUG LOGGING
        logger.info(f"💾 TRANSACTION SAVE:")
        logger.info(f"  - ID: {self.id}")
        logger.info(f"  - No: {self.transaction_no}")
        logger.info(f"  - Company: {self.company.name if self.company else 'None'}")
        logger.info(f"  - Account: {self.account.name if self.account else 'None'}")
        logger.info(f"  - Amount: {self.amount}")
        logger.info(f"  - Type: {self.transaction_type}")
        logger.info(f"  - Is New: {is_new}")

        # Update account balance for completed non-opening transactions
        if is_new and self.status == 'completed' and not self.is_opening_balance:
            logger.info(f"🔄 Updating account balance")
            self._update_account_balance()
        else:
            logger.info(f"⏸️  Skipping balance update")

    def _generate_transaction_no(self):
        """Generate unique transaction number that is company-specific"""
        if not self.company:
            # Fallback if no company
            timestamp = int(timezone.now().timestamp())
            return f"TXN-{timestamp}"
        
        # Get the last transaction number for this company
        last_transaction = Transaction.objects.filter(
            company=self.company
        ).order_by('-id').first()
        
        company_prefix = self.company.name[:3].upper()
        
        if last_transaction and last_transaction.transaction_no:
            try:
                # Try to extract sequential number
                last_number_str = last_transaction.transaction_no.split('-')[-1]
                last_number = int(last_number_str)
                new_number = last_number + 1
            except (ValueError, IndexError):
                # If parsing fails, use timestamp-based approach
                timestamp = int(timezone.now().timestamp())
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                new_number = f"{timestamp}{random_str}"
        else:
            # First transaction for this company
            new_number = 1001
        
        transaction_no = f"{company_prefix}-TXN-{new_number}"
        
        # Ensure uniqueness
        counter = 1
        base_no = transaction_no
        while Transaction.objects.filter(transaction_no=transaction_no).exists():
            transaction_no = f"{base_no}-{counter}"
            counter += 1
            if counter > 100:
                # Ultimate fallback
                timestamp = int(timezone.now().timestamp())
                transaction_no = f"{company_prefix}-TXN-{timestamp}"
                break
        
        return transaction_no

    def _update_account_balance(self):
        """Update account balance based on transaction"""
        try:
            account = self.account
            old_balance = account.balance
            
            logger.info(f"BALANCE UPDATE DEBUG - Before:")
            logger.info(f"  - Account: {account.name}")
            logger.info(f"  - Old Balance: {old_balance}")
            logger.info(f"  - Transaction Type: {self.transaction_type}")
            logger.info(f"  - Amount: {self.amount}")
            
            if self.transaction_type == 'credit':
                account.balance += self.amount
                logger.info(f"💰 CREDIT: Account {account.name} balance updated from {old_balance} to {account.balance} (+{self.amount})")
            elif self.transaction_type == 'debit':
                # Check sufficient balance for regular debit transactions
                if account.balance < self.amount:
                    raise ValidationError(f"Insufficient balance in account {account.name}")
                account.balance -= self.amount
                logger.info(f"💸 DEBIT: Account {account.name} balance updated from {old_balance} to {account.balance} (-{self.amount})")
            
            # Save the updated account balance
            account.save(update_fields=['balance'])
            logger.info(f"✅ Account balance saved successfully")
            
        except Exception as e:
            logger.error(f"❌ Error updating account balance: {e}")
            raise

    def clean(self):
        """Validate the transaction"""
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be greater than 0")
        
        if self.account and self.company and self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")
        
        # Validate debit transactions have sufficient balance
        # BUT skip this check for opening balance transactions
        if (self.transaction_type == 'debit' and self.status == 'completed' and 
            self.account and not self.is_opening_balance and self.amount > self.account.balance):
            raise ValidationError(f"Insufficient balance in account {self.account.name}")

    # ... rest of your model methods
    def reverse(self):
        """Reverse this transaction"""
        if self.status != 'completed':
            raise ValidationError("Only completed transactions can be reversed")
        
        with transaction.atomic():
            # Create reversal transaction
            reversal_type = 'credit' if self.transaction_type == 'debit' else 'debit'
            reversal = Transaction.objects.create(
                company=self.company,
                transaction_type=reversal_type,
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=f"Reversal of {self.transaction_no}",
                created_by=self.created_by,
                status='completed',
                is_opening_balance=False  # Reversals are never opening balance
            )
            
            # Mark original as cancelled
            self.status = 'cancelled'
            self.save(update_fields=['status'])
            
            return reversal

    @property
    def is_debit(self):
        return self.transaction_type == 'debit'

    @property
    def is_credit(self):
        return self.transaction_type == 'credit'

    @classmethod
    def create_for_money_receipt(cls, money_receipt):
        """Create transaction for a money receipt"""
        try:
            if not money_receipt.account:
                logger.error(f"No account set for money receipt {money_receipt.mr_no}")
                return None
            
            transaction_obj = cls.objects.create(
                company=money_receipt.company,
                transaction_type='credit',  # Money receipt is always credit
                amount=money_receipt.amount,
                account=money_receipt.account,
                payment_method=money_receipt.payment_method,
                description=f"Money Receipt {money_receipt.mr_no} - {money_receipt.get_customer_display()}",
                money_receipt=money_receipt,
                created_by=money_receipt.created_by,
                status='completed',
                transaction_date=money_receipt.payment_date,
                is_opening_balance=False
            )
            
            logger.info(f"✅ Transaction created for money receipt: {transaction_obj.transaction_no}")
            return transaction_obj
            
        except Exception as e:
            logger.error(f"Error creating transaction for money receipt {money_receipt.mr_no}: {e}")
            return None

    @classmethod
    def get_account_balance(cls, account):
        """Calculate account balance from transactions (for verification)"""
        credits = cls.objects.filter(
            account=account, 
            status='completed',
            transaction_type='credit',
            is_opening_balance=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        debits = cls.objects.filter(
            account=account, 
            status='completed',
            transaction_type='debit', 
            is_opening_balance=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return credits - debits