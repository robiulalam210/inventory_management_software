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
# models.py - Add this at the top
from decimal import Decimal  # Make sure this is imported
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
    mr_no = models.CharField(max_length=20, blank=True, unique=True)  # Added unique constraint
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    sale_invoice_no = models.CharField(max_length=50, blank=True, null=True)  # ADDED THIS FIELD

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

    def save(self, *args, **kwargs):
        """FIXED: Safe save method with proper company validation"""
        # Check if we're already saving to prevent recursion
        if hasattr(self, '_currently_saving') and self._currently_saving:
            return super().save(*args, **kwargs)
        
        self._currently_saving = True
        
        try:
            is_new = self.pk is None

            # Auto-assign company from customer or sale if not set
            if not self.company:
                if self.customer:
                    self.company = self.customer.company
                elif self.sale:
                    self.company = self.sale.company
                elif hasattr(self, '_request_user') and hasattr(self._request_user, 'company'):
                    self.company = self._request_user.company
                else:
                    raise ValidationError("Company is required")

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
                # Set sale_invoice_no from sale
                if self.sale and not self.sale_invoice_no:
                    self.sale_invoice_no = self.sale.invoice_no
                # Ensure customer is set from sale
                if not self.customer and self.sale.customer:
                    self.customer = self.sale.customer
            else:
                self.payment_type = 'overall'
                self.specific_invoice = False

            # Validate company consistency
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
            # But only if this is not a recursive save
            if (self.payment_status == 'completed' and 
                not hasattr(self, '_payment_already_processed')):
                
                self._payment_already_processed = True
                try:
                    self.process_payment()
                except Exception as e:
                    logger.error(f"Payment processing failed for {self.mr_no}: {e}")
                
                try:
                    self.create_transaction()
                except Exception as e:
                    logger.error(f"Transaction creation failed for {self.mr_no}: {e}")
                
        finally:
            # Clean up the flag
            if hasattr(self, '_currently_saving'):
                delattr(self, '_currently_saving')
            if hasattr(self, '_payment_already_processed'):
                delattr(self, '_payment_already_processed')

    def _generate_mr_no(self):
        """Generate company-specific sequential MR number"""
        if not self.company:
            logger.error("Cannot generate MR number: No company assigned")
            timestamp = int(timezone.now().timestamp())
            return f"MR-{timestamp}"
            
        try:
            # Get last receipt for this company
            last_receipt = MoneyReceipt.objects.filter(
                company=self.company,
                mr_no__isnull=False,
                mr_no__startswith='MR-'
            ).order_by('-mr_no').first()
            
            if last_receipt and last_receipt.mr_no:
                try:
                    # Extract number from "MR-1001" format
                    last_number = int(last_receipt.mr_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing receipts
                    existing_count = MoneyReceipt.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First receipt for this company
                existing_count = MoneyReceipt.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            mr_no = f"MR-{new_number}"
            
            # Check for duplicates
            while MoneyReceipt.objects.filter(mr_no=mr_no).exists():
                new_number += 1
                mr_no = f"MR-{new_number}"
                
            return mr_no
            
        except Exception as e:
            logger.error(f"Error generating mr_no: {e}")
            timestamp = int(timezone.now().timestamp())
            random_suffix = ''.join(random.choices(string.digits, k=4))
            return f"MR-{timestamp}-{random_suffix}"

    def process_payment(self):
        """Process payment based on type"""
        try:
            logger.info(f"Processing payment for {self.mr_no} - Type: {self.payment_type}, Amount: {self.amount}")
            
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
            logger.error(f"Payment processing failed for {self.mr_no}: {str(e)}", exc_info=True)
            return False

    def _process_advance_payment(self):
        """Process advance payment - add to customer balance"""
        if not self.customer:
            logger.error(f"Cannot process advance payment: No customer specified for {self.mr_no}")
            return False

        try:
            # Get fresh customer object
            customer = Customer.objects.get(id=self.customer.id)
            
            # Update customer's advance balance
            customer.advance_balance += self.amount
            customer.save(update_fields=['advance_balance'])
            
            logger.info(f"Advance payment processed for {customer.name}: {self.amount}. New balance: {customer.advance_balance}")
            return True
        except Customer.DoesNotExist:
            logger.error(f"Customer not found for advance payment: {self.mr_no}")
            return False
        except Exception as e:
            logger.error(f"Error processing advance payment for {self.mr_no}: {e}")
            return False

    def _process_specific_invoice_payment(self):
        """Process payment for a specific invoice"""
        if not self.sale:
            logger.error(f"Cannot process specific payment: No sale specified for {self.mr_no}")
            return False

        try:
            from sales.models import Sale
            
            # Get fresh sale object
            sale = Sale.objects.get(id=self.sale.id)
            
            # If sale is already paid, treat as advance
            if sale.due_amount <= 0:
                if sale.customer:
                    # Update customer advance balance
                    sale.customer.advance_balance += self.amount
                    sale.customer.save(update_fields=['advance_balance'])
                    logger.info(f"Payment for paid invoice {sale.invoice_no} treated as advance: {self.amount}")
                return True
            
            # Check if amount exceeds due amount
            if self.amount > sale.due_amount:
                # Only pay the due amount, treat rest as advance
                payment_amount = sale.due_amount
                advance_amount = self.amount - sale.due_amount
                
                # Update sale
                sale.paid_amount += payment_amount
                sale.due_amount = Decimal('0.00')
                sale.payment_status = 'paid'
                
                # Save sale
                sale._skip_money_receipt = True  # Prevent recursive money receipt creation
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'updated_at'])
                
                # Process advance if any
                if advance_amount > 0 and sale.customer:
                    sale.customer.advance_balance += advance_amount
                    sale.customer.save(update_fields=['advance_balance'])
                    logger.info(f"Excess payment {advance_amount} treated as advance for invoice {sale.invoice_no}")
                    
            else:
                # Normal payment
                sale.paid_amount += self.amount
                sale.due_amount -= self.amount
                sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
                
                # Save sale
                sale._skip_money_receipt = True  # Prevent recursive money receipt creation
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'updated_at'])

            logger.info(f"Payment processed for {sale.invoice_no}: {self.amount}. New paid: {sale.paid_amount}, New due: {sale.due_amount}")
            return True
            
        except Sale.DoesNotExist:
            logger.error(f"Sale not found for payment: {self.mr_no}")
            return False
        except Exception as e:
            logger.error(f"Error processing specific invoice payment for {self.mr_no}: {e}")
            return False

    def _process_overall_payment(self):
        """Process payment for all due invoices of the customer"""
        if not self.customer:
            logger.error(f"Cannot process overall payment: No customer specified for {self.mr_no}")
            return False

        try:
            from sales.models import Sale

            # Get fresh customer object
            customer = Customer.objects.get(id=self.customer.id)
            
            # Get all due sales for this customer
            due_sales = Sale.objects.filter(
                customer=customer,
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
                sale.due_amount -= applied
                sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
                
                # Save sale without triggering money receipt
                sale._skip_money_receipt = True
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'updated_at'])
                
                remaining -= applied
                processed_any = True
                logger.info(f"Applied {applied} to invoice {sale.invoice_no}. Remaining: {remaining}")

            # Treat remaining as advance
            if remaining > 0:
                customer.advance_balance += remaining
                customer.save(update_fields=['advance_balance'])
                logger.info(f"Remaining {remaining} added as advance for {customer.name}. New balance: {customer.advance_balance}")

            return processed_any or remaining > 0
            
        except Customer.DoesNotExist:
            logger.error(f"Customer not found for overall payment: {self.mr_no}")
            return False
        except Exception as e:
            logger.error(f"Error processing overall payment for {self.mr_no}: {e}")
            return False

    def create_transaction(self):
        """Create transaction record for this money receipt"""
        if not self.account:
            logger.warning(f"No account specified for money receipt {self.mr_no}")
            return None

        # Check if transaction already exists
        if self.transaction:
            logger.info(f"Money receipt {self.mr_no} already has transaction")
            return self.transaction

        try:
            from transactions.models import Transaction
            transaction = Transaction.create_for_money_receipt(self)
            if transaction:
                # Link the transaction
                self.transaction = transaction
                self.save(update_fields=['transaction'])
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
                # Get fresh sale data
                from sales.models import Sale
                sale = Sale.objects.get(id=self.sale.id)
                
                # Calculate before payment values
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
        """Create money receipt automatically for sale - FIXED VERSION"""
        if sale.paid_amount <= 0:
            return None
        
        # Check if auto receipt already exists for this sale
        existing = cls.objects.filter(sale=sale, payment_type='specific').first()
        if existing:
            logger.info(f"Auto receipt already exists for sale {sale.invoice_no}: {existing.mr_no}")
            return existing

        try:
            receipt = cls(
                company=sale.company,
                customer=sale.customer,
                sale=sale,
                sale_invoice_no=sale.invoice_no,
                payment_type='specific',
                specific_invoice=True,
                amount=sale.paid_amount,
                payment_method=sale.payment_method or 'Cash',
                payment_date=timezone.now(),
                remark=f"Auto receipt for {sale.invoice_no}",
                seller=sale.sale_by,
                account=sale.account,
                created_by=created_by or sale.created_by,
                payment_status='completed'
            )

            # Mark as auto-created to prevent recursion
            receipt._skip_payment_processing = True
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
                sale_invoice_no=None,
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