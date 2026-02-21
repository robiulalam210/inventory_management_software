from django.db import models, transaction as db_transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Company
from accounts.models import Account

class IncomeHead(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name

class Income(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('mobile', 'Mobile Banking'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHOD_CHOICES, default='cash')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    head = models.ForeignKey(IncomeHead, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='incomes')
    income_date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-income_date', '-date_created']

    def __str__(self):
        description = self.note[:50] + '...' if self.note and len(self.note) > 50 else self.note or ''
        return f"{self.invoice_number} - {description} - {self.amount}"

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Income amount must be greater than 0")
        if self.account and self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        self.clean()
        super().save(*args, **kwargs)
        with db_transaction.atomic():
            self.create_income_transaction(is_new=is_new)

    def generate_invoice_number(self):
        if not self.company:
            return f"INC-TEMP-{int(timezone.now().timestamp())}"
        from django.db.models import Max
        from django.db.models.functions import Cast, Substr
        max_income = Income.objects.filter(
            company=self.company,
            invoice_number__regex=r'^INC-\d+$'
        ).aggregate(
            max_number=Max(
                Cast(
                    Substr('invoice_number', 5),
                    output_field=models.IntegerField()
                )
            )
        )
        next_number = (max_income['max_number'] or 1000) + 1
        invoice_number = f"INC-{next_number}"
        counter = 0
        while Income.objects.filter(company=self.company, invoice_number=invoice_number).exists():
            counter += 1
            invoice_number = f"INC-{next_number + counter}"
        return invoice_number

    def create_income_transaction(self, is_new=True):
        if not self.account:
            return
        try:
            from transactions.models import Transaction
            if is_new:
                Transaction.objects.create(
                    company=self.company,
                    transaction_type='credit',
                    amount=self.amount,
                    account=self.account,
                    description=f"Income: {self.head.name if self.head else ''} - {self.note or ''}",
                    reference_no=self.invoice_number,
                    income=self,
                    payment_method=self.payment_method,  # INCLUDE payment method!
                    status='completed',
                    transaction_date=self.income_date,
                    created_by=self.created_by
                )
                self.account.balance += self.amount
                self.account.save(update_fields=['balance'])
                self.account.refresh_from_db()
        except Exception as e:
            import logging, traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating income transaction: {str(e)}")
            logger.error(traceback.format_exc())