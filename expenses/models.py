from django.db import models, transaction as db_transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import Company
from accounts.models import Account
import logging
import traceback

logger = logging.getLogger(__name__)

class ExpenseHead(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

class ExpenseSubHead(models.Model):
    name = models.CharField(max_length=255)
    head = models.ForeignKey(ExpenseHead, related_name='subheads', on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['head__name', 'name']
        indexes = [
            models.Index(fields=['head', 'is_active']),
        ]

    def __str__(self):
        return f"{self.head.name} - {self.name}"
    
    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

class Expense(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('mobile', 'Mobile Banking'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    head = models.ForeignKey(ExpenseHead, on_delete=models.CASCADE)
    subhead = models.ForeignKey(ExpenseSubHead, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default='cash')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='expenses')
    expense_date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-expense_date', '-date_created']
        indexes = [
            models.Index(fields=['company', 'expense_date']),
            models.Index(fields=['head', 'expense_date']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['account', 'expense_date']),
        ]

    def __str__(self):
        description = self.note[:50] + '...' if self.note and len(self.note) > 50 else self.note
        return f"{self.invoice_number} - {description} - {self.amount}"

    def clean(self):
        """Validate expense data"""
        if self.amount <= 0:
            raise ValidationError("Expense amount must be greater than 0")
        
        if self.account and self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")
        
        # Check if account has sufficient balance
        if self.account and self.amount > self.account.balance:
            raise ValidationError(f"Insufficient balance in account. Available: {self.account.balance}")

    def save(self, *args, **kwargs):
        """Save expense with proper transaction handling for both creation and updates"""
        is_new = self.pk is None
        old_instance = None
        old_amount = None
        old_account = None
        
        # If updating, get the old instance data BEFORE saving
        if not is_new:
            try:
                old_instance = Expense.objects.get(pk=self.pk)
                old_amount = old_instance.amount
                old_account = old_instance.account
            except Expense.DoesNotExist:
                old_instance = None
        
        # Generate invoice number if new and not provided
        if is_new and not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # Validate before saving
        self.clean()
        
        # Save the expense first
        super().save(*args, **kwargs)
        
        # Handle transaction logic based on whether it's new or update
        with db_transaction.atomic():  # Use database transaction for consistency
            if is_new:
                # NEW EXPENSE: Create transaction
                if self.account:
                    logger.info(f"Processing new expense {self.invoice_number}")
                    try:
                        transaction = self.create_expense_transaction()
                        if transaction:
                            logger.info(f"SUCCESS: Transaction created: {transaction.id}")
                            self.account.refresh_from_db()
                            logger.info(f" Account balance after transaction: {self.account.balance}")
                        else:
                            logger.error(f"ERROR: Transaction creation failed for expense {self.invoice_number}")
                    except Exception as e:
                        logger.error(f"ERROR: Error in transaction creation: {str(e)}")
                        logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
                else:
                    logger.warning(f"No account specified for new expense {self.invoice_number}")
            
            else:
                # UPDATING EXISTING EXPENSE
                logger.info(f" Processing expense update {self.invoice_number}")
                
                # Get existing transaction
                existing_transaction = self.get_associated_transaction()
                
                # Detect what changed
                amount_changed = old_instance and self.amount != old_amount
                account_changed = old_instance and self.account != old_account
                
                if amount_changed or account_changed:
                    logger.info(f"  - Amount changed: {amount_changed} ({old_amount} → {self.amount})")
                    logger.info(f"  - Account changed: {account_changed} ({old_account} → {self.account})")
                    
                    # Handle the update by reversing old and creating new
                    self._handle_expense_update(old_instance, existing_transaction)
                else:
                    logger.info(f" No significant changes to amount or account - transaction unchanged")
                
    def _handle_expense_update(self, old_instance, existing_transaction):
        """Handle updates to expense by modifying transactions"""
        try:
            from transactions.models import Transaction
            
            # If there was an old account and old transaction, reverse it
            if old_instance and old_instance.account and existing_transaction:
                logger.info(f"Reversing old transaction {existing_transaction.transaction_no}")
                
                # Create a reversal transaction
                reversal = self._create_reversal_transaction(old_instance)
                if reversal:
                    logger.info(f"Reversal created: {reversal.transaction_no}")
                
                # Mark old transaction as cancelled
                existing_transaction.status = 'cancelled'
                existing_transaction.save(update_fields=['status'])
                logger.info(f"Old transaction cancelled: {existing_transaction.transaction_no}")
            
            # If there's a new account (or same account with new amount), create new transaction
            if self.account:
                logger.info(f"Creating new transaction for updated expense")
                new_transaction = self.create_expense_transaction()
                
                if new_transaction:
                    logger.info(f"New transaction created: {new_transaction.transaction_no}")
                    
                    # Refresh account balance
                    self.account.refresh_from_db()
                    logger.info(f"Updated account balance: {self.account.balance}")
                else:
                    logger.error(f"ERROR: Failed to create new transaction for updated expense")
            else:
                logger.info(f"No account specified - no new transaction created")
                
        except Exception as e:
            logger.error(f"ERROR: Error handling expense update: {str(e)}")
            logger.error(f"ERROR: Traceback: {traceback.format_exc()}")

    def _create_reversal_transaction(self, old_instance):
        """Create a reversal transaction for the old expense"""
        try:
            from transactions.models import Transaction
            
            # Create a CREDIT transaction to reverse the old DEBIT
            reversal = Transaction.objects.create(
                company=old_instance.company,
                transaction_type='credit',  # CREDIT to reverse DEBIT
                amount=old_instance.amount,
                account=old_instance.account,
                payment_method=old_instance.payment_method,
                description=f"Reversal - Previous expense: {old_instance.invoice_number}",
                created_by=old_instance.created_by,
                status='completed',
                transaction_date=timezone.now().date(),
                is_opening_balance=False
            )
            
            logger.info(f"Created reversal transaction: {reversal.transaction_no}")
            logger.info(f"Account {old_instance.account.name} balance increased by {old_instance.amount}")
            return reversal
            
        except Exception as e:
            logger.error(f"ERROR: Error creating reversal transaction: {e}")
            return None

    def generate_invoice_number(self):
        """Generate unique invoice number: EXP-1001, EXP-1002, etc."""
        if not self.company:
            # Fallback for expenses without company
            return f"EXP-TEMP-{int(timezone.now().timestamp())}"
        
        try:
            # Use database aggregation to safely get the max number
            from django.db.models import Max
            from django.db.models.functions import Cast, Substr
            
            # Get the current max invoice number for this company
            max_expense = Expense.objects.filter(
                company=self.company,
                invoice_number__regex=r'^EXP-\d+$'
            ).aggregate(
                max_number=Max(
                    Cast(
                        Substr('invoice_number', 5),  # Extract after 'EXP-'
                        output_field=models.IntegerField()
                    )
                )
            )
            
            # Start from max number + 1 or 1001 if no expenses exist
            next_number = (max_expense['max_number'] or 1000) + 1
            
            invoice_number = f"EXP-{next_number}"
            
            # Double-check uniqueness (handles race conditions)
            counter = 0
            while Expense.objects.filter(company=self.company, invoice_number=invoice_number).exists():
                counter += 1
                invoice_number = f"EXP-{next_number + counter}"
                
            return invoice_number
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {str(e)}")
            # Fallback with high precision timestamp
            return f"EXP-{int(timezone.now().timestamp() * 1000)}"
    
    def create_expense_transaction(self):
        """Create DEBIT transaction record for this expense"""
        if not self.account:
            logger.warning(f"No account specified for expense {self.invoice_number}")
            return None

        try:
            # Import inside method to avoid circular imports
            from transactions.models import Transaction
            
            # Create description
            description_parts = [f"Expense: {self.head.name}"]
            if self.subhead:
                description_parts.append(f" - {self.subhead.name}")
            if self.note:
                description_parts.append(f" - {self.note}")
            
            description = ''.join(description_parts)
            
            logger.info(f"🔍 Creating transaction for expense {self.invoice_number}")
            logger.info(f"  - Company: {self.company}")
            logger.info(f"  - Amount: {self.amount}")
            logger.info(f"  - Account: {self.account} (ID: {self.account.id})")
            logger.info(f"  - Payment Method: {self.payment_method}")
            logger.info(f"  - Description: {description}")
            
            # Create transaction
            transaction = Transaction.objects.create(
                company=self.company,
                transaction_type='debit',
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=description,
                reference_no=self.invoice_number,
                expense=self,
                status='completed',
                transaction_date=self.expense_date,
                created_by=self.created_by
            )
            
            logger.info(f"SUCCESS: TRANSACTION CREATED - {transaction.transaction_no}")
            return transaction
            
        except ImportError as e:
            logger.error(f"ERROR: Failed to import Transaction model: {e}")
            return None
            
        except Exception as e:
            logger.error(f"ERROR: Error creating transaction: {str(e)}")
            logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
            return None

    def force_create_transaction(self):
        """Force create a transaction if one doesn't exist"""
        try:
            from transactions.models import Transaction
            
            # Check if transaction already exists
            existing_transaction = Transaction.objects.filter(expense=self).first()
            if existing_transaction:
                logger.info(f"Transaction already exists: {existing_transaction.id}")
                return existing_transaction
            
            # Create new transaction
            return self.create_expense_transaction()
            
        except Exception as e:
            logger.error(f"ERROR: Error in force_create_transaction: {e}")
            return None

    def delete(self, *args, **kwargs):
        """Handle expense deletion - restore account balance and reverse transaction"""
        if self.account:
            try:
                # Restore the amount to account balance (reverse the debit)
                old_balance = self.account.balance
                self.account.balance += self.amount
                self.account.save(update_fields=['balance', 'updated_at'])
                logger.info(f"Account balance restored after deleting expense {self.invoice_number}: {old_balance} → {self.account.balance}")
            except Exception as e:
                logger.error(f"ERROR: Error restoring account balance for deleted expense {self.invoice_number}: {str(e)}")
        
        # Delete associated transaction if exists
        try:
            from transactions.models import Transaction
            transactions = Transaction.objects.filter(expense=self)
            transaction_count = transactions.count()
            if transaction_count > 0:
                transactions.delete()
                logger.info(f"{transaction_count} associated transactions deleted for expense {self.invoice_number}")
            else:
                logger.info(f"No associated transactions found for expense {self.invoice_number}")
        except Exception as e:
            logger.error(f"ERROR: Error deleting associated transactions: {e}")
        
        # Delete the expense
        super().delete(*args, **kwargs)

    @property
    def description(self):
        """Return a descriptive text for the expense"""
        if self.note:
            return self.note
        base_desc = f"{self.head.name}"
        if self.subhead:
            base_desc += f" - {self.subhead.name}"
        return base_desc

    @property
    def status(self):
        """Return status based on expense date"""
        if self.expense_date < timezone.now().date():
            return "Completed"
        elif self.expense_date == timezone.now().date():
            return "Today"
        else:
            return "Upcoming"

    @property
    def is_debit(self):
        """Always True for expenses - they are debit transactions"""
        return True

    def get_expense_summary(self):
        """Get detailed expense summary"""
        summary = {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'head': self.head.name,
            'subhead': self.subhead.name if self.subhead else None,
            'amount': float(self.amount),
            'payment_method': self.get_payment_method_display(),
            'account': self.account.name if self.account else None,
            'expense_date': self.expense_date.isoformat(),
            'note': self.note,
            'status': self.status,
            'created_by': self.created_by.get_full_name() if self.created_by else 'System',
            'is_debit': self.is_debit
        }
        
        # Get associated transaction info
        transaction = self.get_associated_transaction()
        if transaction:
            summary['transaction_id'] = transaction.id
            if hasattr(transaction, 'transaction_no'):
                summary['transaction_no'] = transaction.transaction_no
            summary['transaction_status'] = transaction.status
        else:
            summary['transaction_id'] = None
            summary['transaction_no'] = None
            summary['transaction_status'] = 'Not Created'
        
        return summary

    def get_associated_transaction(self):
        """Get the transaction associated with this expense"""
        try:
            from transactions.models import Transaction
            transaction = Transaction.objects.filter(expense=self).first()
            if transaction:
                logger.info(f"Found associated transaction: {transaction.id}")
            else:
                logger.info(f"No associated transaction found for expense {self.id}")
            return transaction
        except ImportError:
            logger.error("ERROR: Cannot import Transaction model")
            return None
        except Exception as e:
            logger.error(f"ERROR: Error getting associated transaction: {e}")
            return None

    def has_transaction(self):
        """Check if this expense has an associated transaction"""
        transaction = self.get_associated_transaction()
        return transaction is not None

# Add a management command to fix missing transactions
import os
import django
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create missing transactions for expenses'
    
    def handle(self, *args, **options):
        from expenses.models import Expense
        from transactions.models import Transaction
        
        expenses_without_transactions = []
        for expense in Expense.objects.all():
            if not expense.has_transaction() and expense.account:
                self.stdout.write(f"Creating transaction for expense {expense.invoice_number}...")
                transaction = expense.force_create_transaction()
                if transaction:
                    self.stdout.write(self.style.SUCCESS(f"SUCCESS: Created transaction {transaction.id}"))
                    expenses_without_transactions.append(expense.invoice_number)
                else:
                    self.stdout.write(self.style.ERROR(f"ERROR: Failed to create transaction"))
        
        if expenses_without_transactions:
            self.stdout.write(self.style.SUCCESS(f"Fixed {len(expenses_without_transactions)} expenses"))
        else:
            self.stdout.write("No expenses missing transactions")