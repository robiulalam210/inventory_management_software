from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.models import Company
from customers.models import Customer
from accounts.models import Account
from django.contrib.auth import get_user_model
import logging
import random
import string

logger = logging.getLogger(__name__)
User = get_user_model()

class MoneyReceipt(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('overall', 'Overall Payment'),
        ('specific', 'Specific Invoice Payment'),
        ('advance', 'Advance Payment'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mr_no = models.CharField(max_length=20, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='overall')
    specific_invoice = models.BooleanField(default=False)
    is_advance_payment = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100, default='cash')
    payment_date = models.DateTimeField(default=timezone.now)
    remark = models.TextField(null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='money_receipts_sold')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_status = models.CharField(max_length=20, null=True, blank=True)
    cheque_id = models.CharField(max_length=64, null=True, blank=True)

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
            models.Index(fields=['is_advance_payment']),
        ]

    def __str__(self):
        customer_name = self.customer.name if self.customer else 'N/A'
        return f"{self.mr_no} - {customer_name} - {self.amount}"

    def clean(self):
        """Model validation"""
        if self.amount <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        if self.is_advance_payment and not self.customer:
            raise ValidationError("Customer is required for advance payments")
        
        if self.payment_type == 'specific' and not self.sale:
            raise ValidationError("Specific invoice payment must have a sale reference")
        
        if self.payment_type == 'overall' and not self.customer:
            raise ValidationError("Overall payment must have a customer reference")
        
        if self.account and self.account.company != self.company:
            raise ValidationError("Account must belong to the same company")
        
        if self.customer and self.customer.company != self.company:
            raise ValidationError("Customer must belong to the same company")

   # money_receipts/models.py - FIX THE SAVE METHOD

    def save(self, *args, **kwargs):
        """FIXED: Safe save method with proper company validation"""
        # Prevent recursion
        if getattr(self, '_saving', False):
            return super().save(*args, **kwargs)
        
        self._saving = True
        
        try:
            is_new = self.pk is None

            # SUCCESS: FIXED: Auto-assign company from customer or sale if not set
            if not self.company:
                if self.customer:
                    self.company = self.customer.company
                elif self.sale:
                    self.company = self.sale.company
                elif hasattr(self, '_request_user') and hasattr(self._request_user, 'company'):
                    self.company = self._request_user.company

            # Generate MR number if new
            if is_new and not self.mr_no:
                self.mr_no = self._generate_mr_no()

            # Set payment type based on conditions
            if self.is_advance_payment:
                self.payment_type = 'advance'
                self.specific_invoice = False
            elif self.sale:
                self.payment_type = 'specific'
                self.specific_invoice = True
                # Ensure customer is set from sale and validate company
                if not self.customer and self.sale.customer:
                    self.customer = self.sale.customer
                    # SUCCESS: FIXED: Ensure customer company matches
                    if self.customer.company != self.company:
                        logger.warning(f"Customer company mismatch. Resetting customer.")
                        self.customer = None
            else:
                self.payment_type = 'overall'
                self.specific_invoice = False

            # SUCCESS: FIXED: Validate company consistency before clean
            if self.customer and self.customer.company != self.company:
                raise ValidationError("Customer must belong to the same company")
            
            if self.sale and self.sale.company != self.company:
                raise ValidationError("Sale must belong to the same company")
                
            if self.account and self.account.company != self.company:
                raise ValidationError("Account must belong to the same company")

            # Validate before saving
            self.clean()

            # Save the model first
            super().save(*args, **kwargs)

            # Process payment and create transaction if completed
            if (self.payment_status == 'completed' and 
                not getattr(self, '_payment_processed', False)):
                
                self._payment_processed = True
                self.process_payment()
                self.create_transaction()
                
        finally:
            self._saving = False


  # money_receipts/models.py - FIXED _generate_mr_no METHOD

    def _generate_mr_no(self):
        """Generate company-specific sequential MR number - FIXED VERSION"""
        if not self.company:
            logger.error("Cannot generate MR number: No company assigned")
            timestamp = int(timezone.now().timestamp())
            return f"MR-{timestamp}"
            
        try:
            # SUCCESS: FIXED: Get last receipt FOR THIS COMPANY ONLY
            last_receipt = MoneyReceipt.objects.filter(
                company=self.company,  # SUCCESS: Only this company's receipts
                mr_no__isnull=False,
                mr_no__startswith='MR-'
            ).order_by('-mr_no').first()
            
            if last_receipt and last_receipt.mr_no:
                try:
                    # Extract number from "MR-1001" format
                    last_number = int(last_receipt.mr_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing receipts FOR THIS COMPANY
                    existing_count = MoneyReceipt.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First receipt FOR THIS COMPANY
                existing_count = MoneyReceipt.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            mr_no = f"MR-{new_number}"
            
            # Check for duplicates (shouldn't happen with company filter)
            counter = 0
            while MoneyReceipt.objects.filter(company=self.company, mr_no=mr_no).exists() and counter < 10:
                new_number += 1
                mr_no = f"MR-{new_number}"
                counter += 1
                
            return mr_no
            
        except Exception as e:
            logger.error(f"Error generating mr_no: {e}")
            timestamp = int(timezone.now().timestamp())
            return f"MR-{timestamp}"
        
    def process_payment(self):
        """Process payment based on type"""
        try:
            if self.is_advance_payment:
                return self._process_advance_payment()
            elif self.payment_type == 'specific' and self.sale:
                return self._process_specific_invoice_payment()
            else:
                return self._process_overall_payment()
        except Exception as e:
            # Mark as failed if processing fails
            self.payment_status = 'failed'
            self.save(update_fields=['payment_status'])
            logger.error(f"Payment processing failed for {self.mr_no}: {str(e)}")
            return False

    def _process_advance_payment(self):
        """Process advance payment - add to customer balance"""
        if not self.customer:
            logger.error("Cannot process advance payment: No customer specified")
            return False

        try:
            # Update customer's advance balance
            self.customer.advance_balance += self.amount
            self.customer.save(update_fields=['advance_balance'])
            logger.info(f"Advance payment processed for {self.customer.name}: {self.amount}")
            return True
        except Exception as e:
            logger.error(f"Error processing advance payment: {e}")
            return False

    def _process_specific_invoice_payment(self):
        """Process payment for a specific invoice"""
        if not self.sale:
            logger.error("Cannot process specific payment: No sale specified")
            return False

        try:
            from sales.models import Sale
            
            # Get fresh sale object to avoid stale data
            sale = Sale.objects.get(id=self.sale.id)
            
            # If sale is already paid, treat as advance
            if sale.due_amount <= 0:
                if sale.customer:
                    sale.customer.advance_balance += self.amount
                    sale.customer.save(update_fields=['advance_balance'])
                    logger.info(f"Payment for paid invoice {sale.invoice_no} treated as advance: {self.amount}")
                return True
            
            # Validate payment amount
            if self.amount > sale.due_amount:
                # Only pay the due amount, treat rest as advance
                payment_amount = sale.due_amount
                advance_amount = self.amount - sale.due_amount
                
                # Process payment
                sale.paid_amount += payment_amount
                sale.due_amount = Decimal('0.00')
                sale.payment_status = 'paid'
                
                # Save sale WITHOUT triggering money receipt
                sale._skip_money_receipt = True
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
                
                # Process advance if any
                if advance_amount > 0 and sale.customer:
                    sale.customer.advance_balance += advance_amount
                    sale.customer.save(update_fields=['advance_balance'])
                    logger.info(f"Excess payment {advance_amount} treated as advance")
                    
            else:
                # Normal payment
                sale.paid_amount += self.amount
                sale.due_amount = sale.due_amount - self.amount
                sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
                
                # Save sale WITHOUT triggering money receipt
                sale._skip_money_receipt = True
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])

            logger.info(f"Payment processed for {sale.invoice_no}: {self.amount}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing specific invoice payment: {e}")
            return False

    def _process_overall_payment(self):
        """Process payment for all due invoices of the customer"""
        if not self.customer:
            logger.error("Cannot process overall payment: No customer specified")
            return False

        try:
            from sales.models import Sale

            due_sales = Sale.objects.filter(
                customer=self.customer,
                company=self.company,
                due_amount__gt=0
            ).order_by('sale_date')

            remaining = self.amount
            processed_any = False

            for sale in due_sales:
                if remaining <= 0:
                    break

                applied = min(remaining, sale.due_amount)
                sale.paid_amount += applied
                sale.due_amount = sale.due_amount - applied
                sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
                
                # Save sale WITHOUT triggering money receipt
                sale._skip_money_receipt = True
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
                
                remaining -= applied
                processed_any = True
                logger.info(f"Applied {applied} to invoice {sale.invoice_no}")

            # Treat remaining as advance
            if remaining > 0:
                self.customer.advance_balance += remaining
                self.customer.save(update_fields=['advance_balance'])
                logger.info(f"Remaining {remaining} added as advance for {self.customer.name}")

            return processed_any or remaining > 0
            
        except Exception as e:
            logger.error(f"Error processing overall payment: {e}")
            return False

    def create_transaction(self):
        """Create transaction record for this money receipt"""
        if not self.account:
            logger.warning(f"No account specified for money receipt {self.mr_no}")
            return None

        # Check if transaction already exists
        if hasattr(self, 'transaction') and self.transaction:
            logger.info(f"Money receipt {self.mr_no} already has transaction")
            return self.transaction

        try:
            from transactions.models import Transaction
            transaction = Transaction.create_for_money_receipt(self)
            if transaction:
                logger.info(f"Transaction created for money receipt {self.mr_no}: {transaction.transaction_no}")
            return transaction
            
        except Exception as e:
            logger.error(f"Error creating transaction for {self.mr_no}: {e}")
            return None

    def get_payment_summary(self):
        """Get payment summary"""
        summary = {
            'mr_no': self.mr_no,
            'payment_type': self.payment_type,
            'amount': float(self.amount),
            'payment_method': self.payment_method,
            'payment_date': self.payment_date.isoformat(),
            'status': self.payment_status,
            'is_advance_payment': self.is_advance_payment,
        }

        if self.is_advance_payment:
            summary.update({
                'customer': self.customer.name if self.customer else 'Unknown',
                'type': 'advance_payment',
                'new_balance': float(self.customer.advance_balance) if self.customer else 0
            })
        elif self.payment_type == 'specific' and self.sale:
            try:
                from sales.models import Sale
                sale = Sale.objects.get(id=self.sale.id)
                
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
            except Exception as e:
                logger.error(f"Error getting payment summary for sale: {e}")
        
        return summary

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
        """Create money receipt automatically for sale"""
        if sale.paid_amount <= 0:
            return None

        try:
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
            
        except Exception as e:
            logger.error(f"Error creating auto receipt for sale {sale.invoice_no}: {e}")
            return None

    @classmethod
    def create_advance_receipt(cls, customer, amount, payment_method, account, company, created_by=None, seller=None):
        """Create advance payment receipt"""
        try:
            receipt = cls(
                company=company,
                customer=customer,
                sale=None,
                payment_type='advance',
                specific_invoice=False,
                is_advance_payment=True,
                amount=amount,
                payment_method=payment_method,
                payment_date=timezone.now(),
                remark="Advance payment received",
                seller=seller,
                account=account,
                created_by=created_by,
                payment_status='completed'
            )

            receipt.save()
            return receipt
            
        except Exception as e:
            logger.error(f"Error creating advance receipt: {e}")
            return None