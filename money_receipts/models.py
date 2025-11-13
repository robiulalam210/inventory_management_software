# money_receipts/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.models import Company
from customers.models import Customer
from accounts.models import Account
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class MoneyReceipt(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('overall', 'Overall Payment'),
        ('specific', 'Specific Invoice Payment'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mr_no = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)

    # Payment type fields
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='overall')
    specific_invoice = models.BooleanField(default=False)
    
    # Payment status
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100)
    payment_date = models.DateTimeField(default=timezone.now)
    remark = models.TextField(null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='money_receipts_sold')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_status = models.CharField(max_length=20, null=True, blank=True)
    cheque_id = models.CharField(max_length=64, null=True, blank=True)

    # Transaction reference
    transaction = models.OneToOneField(
        'transactions.Transaction', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linked_money_receipt'
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='money_receipts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'payment_date']),
            models.Index(fields=['customer', 'payment_date']),
            models.Index(fields=['mr_no']),
        ]

    def __str__(self):
        customer_name = self.customer.name if self.customer else 'N/A'
        return f"{self.mr_no} - {customer_name} - {self.amount}"

    def clean(self):
        """Model validation"""
        if self.amount <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        if self.payment_type == 'specific' and not self.sale:
            raise ValidationError("Specific invoice payment must have a sale reference")
        
        if self.payment_type == 'overall' and not self.customer:
            raise ValidationError("Overall payment must have a customer reference")
        
        # Validate account belongs to same company
        if self.account and self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")
        
        # Validate customer belongs to same company
        if self.customer and self.customer.company != self.company:
            raise ValidationError("Customer must belong to the same company")

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Generate MR number if new
        if is_new and not self.mr_no:
            self.mr_no = self.generate_mr_no()

        # Set payment type based on sale existence
        if self.sale:
            self.payment_type = 'specific'
            self.specific_invoice = True
            # Ensure customer is set from sale
            if not self.customer and self.sale.customer:
                self.customer = self.sale.customer
        else:
            self.payment_type = 'overall'
            self.specific_invoice = False

        # Validate before saving
        self.clean()

        # Save the model first
        super().save(*args, **kwargs)

        # Process payment and create transaction if completed
        if self.payment_status == 'completed' and not getattr(self, '_auto_created', False):
            self.process_payment()
            self.create_transaction()

    def generate_mr_no(self):
        """Generate unique money receipt number"""
        last_receipt = MoneyReceipt.objects.filter(company=self.company).order_by("-id").first()
        new_id = (last_receipt.id + 1) if last_receipt else 1
        return f"MR-{1000 + new_id}"

    def process_payment(self):
        """
        Process payment based on type and update related sales
        """
        try:
            if self.payment_type == 'specific' and self.sale:
                return self._process_specific_invoice_payment()
            else:
                return self._process_overall_payment()
        except Exception as e:
            # Mark as failed if processing fails
            self.payment_status = 'failed'
            self.save(update_fields=['payment_status'])
            raise ValidationError(f"Payment processing failed: {str(e)}")

    def _process_specific_invoice_payment(self):
        """
        Process payment for a specific invoice
        """
        if not self.sale:
            return False

        # Check if payment amount is valid
        max_allowed = self.sale.due_amount
        if self.amount > max_allowed:
            raise ValidationError(
                f"Payment amount ({self.amount}) cannot be greater than due amount ({max_allowed})"
            )

        # Update sale
        sale = self.sale
        sale.paid_amount += self.amount
        sale.due_amount = max(sale.due_amount - self.amount, 0)
        sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
        sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])

        logger.info(f"Payment processed for invoice {sale.invoice_no}: {self.amount} Taka")
        return True

    def _process_overall_payment(self):
        """
        Process payment for all due invoices of the customer
        """
        from sales.models import Sale

        if not self.customer:
            raise ValidationError("Customer is required for overall payment")

        due_sales = Sale.objects.filter(
            customer=self.customer,
            company=self.company,
            due_amount__gt=0
        ).order_by('sale_date')

        remaining = self.amount
        applied_invoices = []

        for sale in due_sales:
            if remaining <= 0:
                break

            applied = min(remaining, sale.due_amount)
            sale.paid_amount += applied
            sale.due_amount = max(sale.due_amount - applied, 0)
            sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
            sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
            
            applied_invoices.append({
                'sale': sale,
                'amount_applied': applied
            })
            remaining -= applied

        return True

    def create_transaction(self):
        """
        Create a transaction record for this money receipt
        Only create if no transaction exists and if not linked to a sale that already created one
        """
        # Don't create transaction if no account
        if not self.account:
            logger.warning("No account specified for money receipt transaction")
            return None

        # Check if transaction already exists
        if self.transaction:
            logger.info(f"Money receipt {self.mr_no} already has transaction: {self.transaction.transaction_no}")
            return self.transaction

        # If this money receipt is linked to a sale, check if sale already created a transaction
        if self.sale and hasattr(self.sale, 'transactions'):
            sale_transactions = self.sale.transactions.filter(status='completed')
            if sale_transactions.exists():
                logger.info(f"Sale {self.sale.invoice_no} already has transactions, skipping money receipt transaction")
                # Link to the first sale transaction instead of creating new one
                self.transaction = sale_transactions.first()
                self.save(update_fields=['transaction'])
                return self.transaction

        try:
            from transactions.models import Transaction
            
            # Create credit transaction (money receipt increases account balance)
            transaction = Transaction.objects.create(
                company=self.company,
                transaction_type='credit',
                amount=self.amount,
                account=self.account,
                payment_method=self.payment_method,
                description=f"Money Receipt {self.mr_no} - {self.get_customer_display()}",
                money_receipt=self,
                created_by=self.created_by,
                status='completed'
            )
            
            # Link transaction to money receipt
            self.transaction = transaction
            self.save(update_fields=['transaction'])
            
            logger.info(f"Transaction created for money receipt: {transaction.transaction_no}")
            return transaction
            
        except ImportError as e:
            logger.error(f"Failed to import Transaction model: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating transaction for money receipt: {e}")
            return None
    def get_payment_summary(self):
        """
        Returns a dictionary summary of the payment
        """
        summary = {
            'mr_no': self.mr_no,
            'payment_type': self.payment_type,
            'amount': float(self.amount),
            'payment_method': self.payment_method,
            'payment_date': self.payment_date.isoformat(),
            'status': self.payment_status,
        }

        if self.payment_type == 'specific' and self.sale:
            sale = self.sale
            previous_paid = float(sale.paid_amount - self.amount)
            previous_due = float(sale.due_amount + self.amount)

            summary.update({
                'invoice_no': sale.invoice_no,
                'before_payment': {
                    'invoice_total': float(sale.grand_total),
                    'previous_paid': previous_paid,
                    'previous_due': previous_due,
                },
                'after_payment': {
                    'current_paid': float(sale.paid_amount),
                    'current_due': float(sale.due_amount),
                    'payment_applied': float(self.amount),
                },
                'invoice_status': 'paid' if sale.due_amount == 0 else 'partial'
            })

        else:
            from sales.models import Sale
            from django.db.models import Sum

            total_due_before = Sale.objects.filter(
                customer=self.customer,
                company=self.company,
                due_amount__gt=0
            ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0

            total_due_after = max(total_due_before - self.amount, 0)

            summary.update({
                'customer': self.customer.name if self.customer else 'Unknown',
                'before_payment': {'total_due': float(total_due_before)},
                'after_payment': {
                    'total_due': float(total_due_after),
                    'payment_applied': float(self.amount)
                },
                'affected_invoices': self.get_affected_invoices(),
                'overall_status': 'completed' if total_due_after == 0 else 'partial'
            })

        return summary

    def get_affected_invoices(self):
        """
        Returns list of invoices affected by this receipt
        """
        from sales.models import Sale

        affected = []
        
        if self.payment_type == 'specific' and self.sale:
            affected.append({
                'invoice_no': self.sale.invoice_no,
                'amount_applied': float(self.amount),
                'previous_due': float(self.sale.due_amount + self.amount),
                'current_due': float(self.sale.due_amount)
            })
        else:
            # For overall payments, we need to calculate which invoices were paid
            due_sales = Sale.objects.filter(
                customer=self.customer,
                company=self.company,
                due_amount__gt=0
            ).order_by('sale_date')

            remaining = self.amount
            for sale in due_sales:
                if remaining <= 0:
                    break

                applied = min(remaining, sale.due_amount)
                affected.append({
                    'invoice_no': sale.invoice_no,
                    'amount_applied': float(applied),
                    'previous_due': float(sale.due_amount + applied),
                    'current_due': float(sale.due_amount)
                })
                remaining -= applied

        return affected

    def get_customer_display(self):
        """Get customer display name"""
        if self.customer:
            return self.customer.name
        elif self.sale and self.sale.customer:
            return self.sale.customer.name
        return "Unknown Customer"

    @property
    def is_specific_payment(self):
        return self.payment_type == 'specific'

    @property
    def is_overall_payment(self):
        return self.payment_type == 'overall'

    @classmethod
    def create_auto_receipt(cls, sale, created_by=None):
        """
        Create a MoneyReceipt automatically without processing payment
        Used for sales that already have payment processing
        """
        if sale.paid_amount <= 0:
            return None

        receipt = cls(
            company=sale.company,
            customer=sale.customer,
            sale=sale,
            payment_type='specific',
            specific_invoice=True,
            amount=sale.paid_amount,
            payment_method=sale.payment_method or 'Cash',
            payment_date=timezone.now(),
            remark=f"Auto-generated receipt - {sale.invoice_no}",
            seller=sale.sale_by,
            account=sale.account,
            created_by=created_by or sale.created_by,
            payment_status='completed'
        )

        setattr(receipt, '_auto_created', True)
        receipt.save()
        
        return receipt

    @classmethod
    def get_customer_payment_summary(cls, customer, company):
        """
        Get payment summary for a customer
        """
        from django.db.models import Sum
        
        receipts = cls.objects.filter(
            customer=customer,
            company=company,
            payment_status='completed'
        )
        
        total_received = receipts.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return {
            'customer': customer.name,
            'total_receipts': receipts.count(),
            'total_amount_received': float(total_received),
            'receipts': list(receipts.values('mr_no', 'amount', 'payment_date'))
        }