# expenses/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import Company
from accounts.models import Account
import logging

logger = logging.getLogger(__name__)

class ExpenseHead(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
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
        is_new = self.pk is None
        
        # Generate invoice number if new
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # Validate before saving
        self.clean()
        
        # Save the expense
        super().save(*args, **kwargs)
        
        # Update account balance and create transaction
        if is_new and self.account:
            self.update_account_balance()
            self.create_expense_transaction()

    def generate_invoice_number(self):
        """Generate simple invoice number: EXP-1001, EXP-1002, etc."""
        if not self.company:
            return None
            
        last_invoice = Expense.objects.filter(
            company=self.company,
            invoice_number__startswith='EXP-'
        ).order_by('-invoice_number').first()
        
        if last_invoice and last_invoice.invoice_number:
            try:
                last_number = int(last_invoice.invoice_number.split('-')[1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1001
        else:
            next_number = 1001
        
        return f"EXP-{next_number}"

    def update_account_balance(self):
        """Update account balance for expense payment"""
        if self.account and self.amount > 0:
            try:
                # Expense decreases account balance (debit)
                self.account.balance -= self.amount
                self.account.save(update_fields=['balance'])
                logger.info(f"Account balance updated for expense {self.invoice_number}")
            except Exception as e:
                logger.error(f"Error updating account balance for expense {self.invoice_number}: {str(e)}")

    def create_expense_transaction(self):
        """Create transaction record for this expense"""
        if not self.account:
            logger.warning(f"No account specified for expense {self.invoice_number}")
            return None

        try:
            from transactions.models import Transaction
            
            transaction = Transaction.objects.create(
                company=self.company,
                transaction_type='debit',  # Expense decreases account balance
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=f"Expense: {self.head.name}" + (f" - {self.subhead.name}" if self.subhead else "") + f" - {self.note or 'No description'}",
                created_by=self.created_by,
                expense=self,
                status='completed'
            )
            
            logger.info(f"Transaction created for expense: {transaction.transaction_no}")
            return transaction
            
        except ImportError as e:
            logger.error(f"Failed to import Transaction model: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating transaction for expense {self.invoice_number}: {e}")
            return None

    def delete(self, *args, **kwargs):
        """Handle expense deletion - restore account balance"""
        if self.account:
            try:
                # Restore the amount to account balance
                self.account.balance += self.amount
                self.account.save(update_fields=['balance'])
                logger.info(f"Account balance restored after deleting expense {self.invoice_number}")
            except Exception as e:
                logger.error(f"Error restoring account balance for deleted expense {self.invoice_number}: {str(e)}")
        
        # Delete the expense
        super().delete(*args, **kwargs)

    @property
    def description(self):
        """Return a descriptive text for the expense"""
        if self.note:
            return self.note
        return f"{self.head.name}" + (f" - {self.subhead.name}" if self.subhead else "")

    @property
    def status(self):
        """Return status based on expense date"""
        if self.expense_date < timezone.now().date():
            return "Completed"
        elif self.expense_date == timezone.now().date():
            return "Today"
        else:
            return "Upcoming"

    def get_expense_summary(self):
        """Get detailed expense summary"""
        return {
            'invoice_number': self.invoice_number,
            'head': self.head.name,
            'subhead': self.subhead.name if self.subhead else None,
            'amount': float(self.amount),
            'payment_method': self.payment_method,
            'account': self.account.name if self.account else None,
            'expense_date': self.expense_date.isoformat(),
            'note': self.note,
            'status': self.status
        }

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
            average_amount=models.Avg('amount')
        )