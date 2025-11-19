# expenses/models.py
from django.db import models
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
    invoice_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

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

    # def save(self, *args, **kwargs):
    #     is_new = self.pk is None
        
    #     # Generate invoice number if new and not provided
    #     if is_new and not self.invoice_number:
    #         self.invoice_number = self.generate_invoice_number()
        
    #     # Validate before saving
    #     self.clean()
        
    #     # Save the expense
    #     super().save(*args, **kwargs)
        
    #     # Update account balance and create transaction for new expenses
    #     if is_new and self.account:
    #         logger.info(f"🔄 Creating transaction for new expense {self.invoice_number}")
    #         try:
    #             self.update_account_balance()
    #             transaction = self.create_expense_transaction()
    #             if transaction:
    #                 logger.info(f"✅ Transaction created successfully: {transaction.id}")
    #             else:
    #                 logger.error(f"❌ Transaction creation returned None for expense {self.invoice_number}")
    #         except Exception as e:
    #             logger.error(f"❌ Error in transaction creation process: {str(e)}")
    #             logger.error(f"❌ Traceback: {traceback.format_exc()}")
    #     else:
    #         if not is_new:
    #             logger.info(f"ℹ️ Expense update - no transaction created for {self.invoice_number}")
    #         if not self.account:
    #             logger.warning(f"⚠️ No account specified for expense {self.invoice_number} - skipping transaction")
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Generate invoice number if new and not provided
        if is_new and not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # Validate before saving
        self.clean()
        
        # Save the expense first
        super().save(*args, **kwargs)
        
        # For NEW expenses with account: Create transaction ONLY (no direct balance update)
        if is_new and self.account:
            logger.info(f"🔄 Processing new expense {self.invoice_number}")
            try:
                # ONLY create transaction - DO NOT update balance directly
                # The transaction's save() method will handle balance update
                transaction = self.create_expense_transaction()
                if transaction:
                    logger.info(f"✅ Transaction created successfully: {transaction.id}")
                    # Verify account balance after transaction
                    self.account.refresh_from_db()
                    logger.info(f"💰 Account balance after transaction: {self.account.balance}")
                else:
                    logger.error(f"❌ Transaction creation returned None for expense {self.invoice_number}")
            except Exception as e:
                logger.error(f"❌ Error in transaction creation process: {str(e)}")
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
        else:
            if not is_new:
                logger.info(f"ℹ️ Expense update - no transaction created for {self.invoice_number}")
            if not self.account:
                logger.warning(f"⚠️ No account specified for expense {self.invoice_number} - skipping transaction")

                
    def generate_invoice_number(self):
        """Generate unique invoice number: EXP-1001, EXP-1002, etc."""
        if not self.company:
            return f"EXP-{int(timezone.now().timestamp())}"
            
        try:
            # Get the last invoice number for this company
            last_expense = Expense.objects.filter(
                company=self.company,
                invoice_number__startswith='EXP-'
            ).order_by('-invoice_number').first()
            
            if last_expense and last_expense.invoice_number:
                try:
                    # Extract number from "EXP-1001" format
                    last_number = int(last_expense.invoice_number.split('-')[1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing expenses
                    existing_count = Expense.objects.filter(company=self.company).count()
                    next_number = 1001 + existing_count
            else:
                # First expense for this company
                existing_count = Expense.objects.filter(company=self.company).count()
                next_number = 1001 + existing_count
            
            invoice_number = f"EXP-{next_number}"
            
            # Ensure uniqueness
            counter = 1
            while Expense.objects.filter(invoice_number=invoice_number).exists():
                invoice_number = f"EXP-{next_number + counter}"
                counter += 1
                
            return invoice_number
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {str(e)}")
            # Fallback: timestamp-based numbering
            return f"EXP-{int(timezone.now().timestamp())}"

    # def update_account_balance(self):
    #     """Update account balance for expense payment - DEBIT transaction"""
    #     if self.account and self.amount > 0:
    #         try:
    #             # Expense decreases account balance (DEBIT - money going out)
    #             old_balance = self.account.balance
    #             self.account.balance -= self.amount
    #             self.account.save(update_fields=['balance', 'updated_at'])
    #             logger.info(f"✅ Account balance updated for expense {self.invoice_number}: {old_balance} -> {self.account.balance}")
    #         except Exception as e:
    #             logger.error(f"❌ Error updating account balance for expense {self.invoice_number}: {str(e)}")
    #             raise

    def create_expense_transaction(self):
        """Create DEBIT transaction record for this expense - GUARANTEED VERSION"""
        if not self.account:
            logger.warning(f"No account specified for expense {self.invoice_number}")
            return None

        try:
            # Import inside method to avoid circular imports
            logger.info("🔍 Importing Transaction model...")
            from transactions.models import Transaction
            logger.info("✅ Transaction model imported successfully")
            
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
            
            # Create transaction data with ALL required fields
            transaction_data = {
                'company': self.company,
                'transaction_type': 'debit',
                'amount': self.amount,
                'account': self.account,
                'payment_method': self.payment_method,
                'description': description,
                'reference_no': self.invoice_number,
                'expense': self,
                'status': 'completed',
                'transaction_date': self.expense_date
            }
            
            # Add created_by if available
            if self.created_by:
                transaction_data['created_by'] = self.created_by
            
            logger.info(f"🔍 Final transaction data: {transaction_data}")
            
            # CREATE THE TRANSACTION
            logger.info("🚀 Creating Transaction object...")
            transaction = Transaction(**transaction_data)
            
            # Check if transaction has required fields
            logger.info(f"🔍 Transaction object created, checking fields...")
            
            # Save the transaction
            transaction.save()
            logger.info(f"✅ TRANSACTION SAVED SUCCESSFULLY! ID: {transaction.id}")
            
            # Verify the transaction was created
            if Transaction.objects.filter(id=transaction.id).exists():
                logger.info(f"✅ Transaction verified in database: {transaction.id}")
                
                # Check if transaction_no exists
                if hasattr(transaction, 'transaction_no'):
                    logger.info(f"✅ Transaction number: {transaction.transaction_no}")
                else:
                    logger.info("ℹ️ No transaction_no field found")
                    
            else:
                logger.error("❌ Transaction not found in database after save!")
                
            return transaction
            
        except ImportError as e:
            logger.error(f"❌ FAILED TO IMPORT TRANSACTION MODEL: {e}")
            logger.error("❌ Please check:")
            logger.error("  1. 'transactions' app is in INSTALLED_APPS")
            logger.error("  2. Transaction model exists in transactions/models.py")
            logger.error("  3. No circular imports")
            return None
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR CREATING TRANSACTION: {str(e)}")
            logger.error(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            
            # Try alternative approach - create with minimal fields
            try:
                logger.info("🔄 Trying alternative transaction creation...")
                from transactions.models import Transaction
                
                # Create with minimal required fields only
                minimal_transaction = Transaction.objects.create(
                    company=self.company,
                    transaction_type='debit',
                    amount=self.amount,
                    account=self.account,
                    description=f"Expense: {self.head.name}",
                    status='completed'
                )
                logger.info(f"✅ Alternative transaction created: {minimal_transaction.id}")
                return minimal_transaction
                
            except Exception as alt_error:
                logger.error(f"❌ Alternative approach also failed: {alt_error}")
                return None

    def force_create_transaction(self):
        """Force create a transaction if one doesn't exist"""
        try:
            from transactions.models import Transaction
            
            # Check if transaction already exists
            existing_transaction = Transaction.objects.filter(expense=self).first()
            if existing_transaction:
                logger.info(f"ℹ️ Transaction already exists: {existing_transaction.id}")
                return existing_transaction
            
            # Create new transaction
            return self.create_expense_transaction()
            
        except Exception as e:
            logger.error(f"❌ Error in force_create_transaction: {e}")
            return None

    def delete(self, *args, **kwargs):
        """Handle expense deletion - restore account balance and reverse transaction"""
        if self.account:
            try:
                # Restore the amount to account balance (reverse the debit)
                old_balance = self.account.balance
                self.account.balance += self.amount
                self.account.save(update_fields=['balance', 'updated_at'])
                logger.info(f"🔄 Account balance restored after deleting expense {self.invoice_number}: {old_balance} -> {self.account.balance}")
            except Exception as e:
                logger.error(f"❌ Error restoring account balance for deleted expense {self.invoice_number}: {str(e)}")
        
        # Delete associated transaction if exists
        try:
            from transactions.models import Transaction
            transactions = Transaction.objects.filter(expense=self)
            transaction_count = transactions.count()
            if transaction_count > 0:
                transactions.delete()
                logger.info(f"🗑️ {transaction_count} associated transactions deleted for expense {self.invoice_number}")
            else:
                logger.info(f"ℹ️ No associated transactions found for expense {self.invoice_number}")
        except Exception as e:
            logger.error(f"❌ Error deleting associated transactions: {e}")
        
        # Delete the expense
        super().delete(*args, **kwargs)

    def reverse_expense(self):
        """Reverse an expense - useful for corrections"""
        if not self.account:
            return False
            
        try:
            # Restore account balance - CREDIT to reverse the DEBIT
            self.account.balance += self.amount
            self.account.save(update_fields=['balance', 'updated_at'])
            
            # Create a reversal transaction (CREDIT to reverse the original DEBIT)
            from transactions.models import Transaction
            
            reversal_transaction = Transaction.objects.create(
                company=self.company,
                transaction_type='credit',
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=f"Reversal of Expense: {self.description}",
                reference_no=f"REV-{self.invoice_number}",
                created_by=self.created_by,
                status='completed',
                transaction_date=timezone.now().date()
            )
            
            logger.info(f"🔄 Expense reversed via CREDIT transaction: {self.invoice_number}")
            return reversal_transaction
            
        except Exception as e:
            logger.error(f"❌ Error reversing expense {self.invoice_number}: {e}")
            return False

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

    @classmethod
    def get_company_expenses(cls, company, start_date=None, end_date=None, head=None):
        """Get expenses for a company with optional filters"""
        queryset = cls.objects.filter(company=company)
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        if head:
            queryset = queryset.filter(head=head)
            
        return queryset.select_related('head', 'subhead', 'account', 'created_by')

    @classmethod
    def get_company_expenses_summary(cls, company, start_date=None, end_date=None):
        """Get expenses summary for a company"""
        queryset = cls.objects.filter(company=company)
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
            
        return queryset.aggregate(
            total_expenses=models.Count('id'),
            total_amount=models.Sum('amount'),
            average_amount=models.Avg('amount'),
            min_amount=models.Min('amount'),
            max_amount=models.Max('amount')
        )

    @classmethod
    def get_expenses_by_head(cls, company, start_date=None, end_date=None):
        """Get expenses grouped by head"""
        from django.db.models import Sum
        
        queryset = cls.objects.filter(company=company)
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
            
        return queryset.values(
            'head__name'
        ).annotate(
            total_amount=Sum('amount'),
            expense_count=models.Count('id')
        ).order_by('-total_amount')

    def get_associated_transaction(self):
        """Get the transaction associated with this expense"""
        try:
            from transactions.models import Transaction
            transaction = Transaction.objects.filter(expense=self).first()
            if transaction:
                logger.info(f"🔍 Found associated transaction: {transaction.id}")
            else:
                logger.info(f"🔍 No associated transaction found for expense {self.id}")
            return transaction
        except ImportError:
            logger.error("❌ Cannot import Transaction model")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting associated transaction: {e}")
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
                    self.stdout.write(self.style.SUCCESS(f"✅ Created transaction {transaction.id}"))
                    expenses_without_transactions.append(expense.invoice_number)
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Failed to create transaction"))
        
        if expenses_without_transactions:
            self.stdout.write(self.style.SUCCESS(f"Fixed {len(expenses_without_transactions)} expenses"))
        else:
            self.stdout.write("No expenses missing transactions")