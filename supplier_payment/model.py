# supplier_payment/models.py
from django.db import models, transaction
from django.core.exceptions import ValidationError
from core.models import Company
from suppliers.models import Supplier
from purchases.models import Purchase
from accounts.models import Account
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class SupplierPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK = 'bank', 'Bank Transfer'
        CHEQUE = 'cheque', 'Cheque'
        MOBILE = 'mobile', 'Mobile Banking'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class PaymentType(models.TextChoices):
        SPECIFIC = 'specific', 'Specific Bill Payment'
        OVERALL = 'overall', 'Overall Payment'
        ADVANCE = 'advance', 'Advance Payment'

    # Basic information
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE)
    
    # Payment identification
    sp_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    # Payment type and details
    payment_type = models.CharField(
        max_length=20, 
        choices=PaymentType.choices, 
        default=PaymentType.OVERALL
    )
    purchase = models.ForeignKey(
        'purchases.Purchase', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='supplier_payments'
    )
    
    # Payment details
    payment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(
        max_length=20, 
        choices=PaymentMethod.choices, 
        default=PaymentMethod.CASH
    )
    
    # Account information
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_payments'
    )
    
    # Advance payment handling
    use_advance = models.BooleanField(default=False)
    advance_amount_used = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Reference and description
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Status - CHANGE DEFAULT TO COMPLETED FOR TESTING
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.COMPLETED  # CHANGED from 'pending' to 'completed'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='supplier_payments_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Supplier Payment'
        verbose_name_plural = 'Supplier Payments'
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'payment_date']),
            models.Index(fields=['supplier', 'payment_date']),
            models.Index(fields=['sp_no']),
        ]

    def __str__(self):
        return f"{self.sp_no} - {self.supplier.name} - ৳{self.amount}"

    def clean(self):
        """Validate payment data"""
        errors = {}
        
        # Validate payment type consistency
        if self.payment_type == 'specific' and not self.purchase:
            errors['purchase'] = 'Purchase must be selected for specific bill payments'
        
        if self.payment_type == 'advance' and self.purchase:
            errors['purchase'] = 'Purchase should not be selected for advance payments'
        
        # Validate amount
        if self.amount <= 0:
            errors['amount'] = 'Payment amount must be greater than 0'
        
        # Validate advance usage
        if self.use_advance:
            if self.advance_amount_used <= 0:
                errors['advance_amount_used'] = 'Advance amount used must be greater than 0'
            
            if self.advance_amount_used > self.supplier.advance_balance:
                errors['advance_amount_used'] = f'Advance amount used ({self.advance_amount_used}) exceeds available advance balance ({self.supplier.advance_balance})'
            
            if self.advance_amount_used > self.amount:
                errors['advance_amount_used'] = 'Advance amount used cannot be greater than total payment amount'
        
        # Validate account for cash payments
        cash_amount = self.amount
        if self.use_advance:
            cash_amount = self.amount - self.advance_amount_used
        
        if cash_amount > 0 and not self.account:
            errors['account'] = 'Account is required for cash payments'
        
        # Validate account balance for cash portion
        if cash_amount > 0 and self.account:
            # Refresh account to get current balance
            current_account = Account.objects.get(id=self.account.id)
            if cash_amount > current_account.balance:
                errors['amount'] = f'Insufficient balance in account {current_account.name}. Available: {current_account.balance}, Required: {cash_amount}'
        
        if errors:
            raise ValidationError(errors)

    def generate_sp_no(self):
        """Generate unique supplier payment number"""
        try:
            last_payment = SupplierPayment.objects.filter(
                company=self.company
            ).order_by('-id').first()
            
            if last_payment and last_payment.sp_no:
                try:
                    # Extract number from "SP-1001" format
                    last_number = int(last_payment.sp_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, count existing payments
                    existing_count = SupplierPayment.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                # First payment for this company
                existing_count = SupplierPayment.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
                
            sp_no = f"SP-{new_number}"
            
            # Ensure uniqueness
            counter = 1
            while SupplierPayment.objects.filter(sp_no=sp_no).exists():
                sp_no = f"SP-{new_number + counter}"
                counter += 1
                if counter > 100:
                    # Fallback with timestamp
                    timestamp = int(timezone.now().timestamp())
                    sp_no = f"SP-{timestamp}"
                    break
                    
            return sp_no
            
        except Exception as e:
            logger.error(f"Error generating SP number: {e}")
            timestamp = int(timezone.now().timestamp())
            return f"SP-{timestamp}"

    def save(self, *args, **kwargs):
        """Save with proper validation and payment processing"""
        is_new = self.pk is None

        # Generate SP number for new payments
        if is_new and not self.sp_no:
            self.sp_no = self.generate_sp_no()

        # Auto-set payment type based on purchase
        if self.purchase:
            self.payment_type = 'specific'
        elif self.payment_type != 'advance':
            self.payment_type = 'overall'

        # Validate before saving
        self.clean()

        # Use atomic transaction for data consistency
        with transaction.atomic():
            # Save the payment record first
            super().save(*args, **kwargs)
            
            # Process payment if new and completed
            if is_new and self.status == 'completed':
                logger.info(f"🆕 NEW PAYMENT DETECTED: {self.sp_no}")
                logger.info(f"💰 Processing payment and creating transaction...")
                
                # Process the payment first (updates account balances, etc.)
                self._process_payment()
                
                # Then create transaction record
                logger.info(f"💳 Creating transaction record...")
                transaction_obj = self._create_transaction()
                
                if transaction_obj:
                    logger.info(f"✅ Payment {self.sp_no} completed with transaction: {transaction_obj.transaction_no}")
                else:
                    logger.warning(f"⚠️  Payment {self.sp_no} completed but no transaction was created")

    def _process_payment(self):
        """Process the payment based on type and advance usage"""
        logger.info(f"🔄 Processing supplier payment: {self.sp_no}, Type: {self.payment_type}, Amount: {self.amount}")
        
        try:
            if self.payment_type == 'advance':
                self._process_advance_payment()
            elif self.payment_type == 'specific':
                self._process_specific_payment()
            else:  # overall
                self._process_overall_payment()
                
            logger.info(f"✅ Successfully processed payment: {self.sp_no}")
            
        except Exception as e:
            logger.error(f"❌ Error processing payment {self.sp_no}: {e}")
            self.status = 'failed'
            super().save(update_fields=['status', 'updated_at'])
            raise

    def _create_transaction(self):
        """Create transaction record for this payment"""
        try:
            from transactions.models import Transaction
            
            # Calculate cash amount for transaction (only cash portion creates transaction)
            cash_amount = self.amount
            if self.use_advance:
                cash_amount = self.amount - self.advance_amount_used
            
            # Only create transaction if there's a cash portion and account
            if cash_amount > 0 and self.account:
                logger.info(f"💾 Creating transaction for cash portion: {cash_amount}")
                
                # Check if transaction already exists via reverse relation
                if hasattr(self, 'transactions') and self.transactions.exists():
                    existing_transaction = self.transactions.first()
                    logger.info(f"⏩ Transaction already exists: {existing_transaction.transaction_no}")
                    return existing_transaction
                
                # Create transaction using the class method
                transaction_obj = Transaction.create_for_supplier_payment(self, cash_amount)
                
                if transaction_obj:
                    logger.info(f"✅ Transaction created successfully: {transaction_obj.transaction_no}")
                    logger.info(f"🔗 Transaction linked to supplier payment: {self.sp_no}")
                    return transaction_obj
                else:
                    logger.error(f"❌ Failed to create transaction for supplier payment {self.sp_no}")
                    return None
            else:
                logger.info(f"⏩ No transaction created - Cash amount: {cash_amount}, Account: {self.account}")
                return None
                
        except ImportError as e:
            logger.error(f"❌ Failed to import Transaction model: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error creating transaction for supplier payment {self.sp_no}: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None

    def _process_advance_payment(self):
        """Process advance payment to supplier"""
        logger.info(f"💰 Processing ADVANCE payment: {self.amount}")
        
        # Refresh supplier to get latest data
        self.supplier.refresh_from_db()
        old_advance = self.supplier.advance_balance
        
        # Increase supplier's advance balance
        self.supplier.advance_balance += self.amount
        self.supplier.save(update_fields=['advance_balance', 'updated_at'])
        
        logger.info(f"✅ Advance balance updated: {old_advance} -> {self.supplier.advance_balance}")
        
        # Decrease account balance
        if self.account:
            old_balance = self.account.balance
            self.account.balance -= self.amount
            self.account.save(update_fields=['balance'])
            logger.info(f"🏦 Account balance updated: {old_balance} -> {self.account.balance}")

    def _process_specific_payment(self):
        """Process payment for specific purchase"""
        if not self.purchase:
            raise ValueError("Purchase is required for specific payments")
        
        logger.info(f"🧾 Processing SPECIFIC payment for purchase: {self.purchase.invoice_no}")
        
        # Refresh purchase data
        self.purchase.refresh_from_db()
        
        # Calculate amounts
        advance_used = self.advance_amount_used if self.use_advance else Decimal('0.00')
        cash_amount = self.amount - advance_used
        
        # Validate purchase due amount
        total_applied = advance_used + cash_amount
        if total_applied > self.purchase.due_amount:
            raise ValueError(
                f"Payment amount ({total_applied}) exceeds purchase due amount ({self.purchase.due_amount})"
            )
        
        # Apply advance payment if used
        if self.use_advance and advance_used > 0:
            if advance_used > self.supplier.advance_balance:
                raise ValueError(f"Advance balance insufficient: {advance_used} > {self.supplier.advance_balance}")
            
            # Use advance for payment
            old_advance = self.supplier.advance_balance
            self.supplier.advance_balance -= advance_used
            self.supplier.save(update_fields=['advance_balance', 'updated_at'])
            logger.info(f"💰 Advance used: {advance_used}, New balance: {self.supplier.advance_balance}")
            
            # Apply advance to purchase
            old_paid = self.purchase.paid_amount
            self.purchase.paid_amount += advance_used
            self.purchase.due_amount = max(Decimal('0.00'), self.purchase.grand_total - self.purchase.paid_amount)
            self.purchase._update_payment_status()
            logger.info(f"🧾 Purchase paid updated: {old_paid} -> {self.purchase.paid_amount}")
        
        # Apply cash payment if any
        if cash_amount > 0:
            if not self.account:
                raise ValueError("Account is required for cash payments")
            
            # Validate account balance
            if cash_amount > self.account.balance:
                raise ValueError(f"Insufficient account balance: {cash_amount} > {self.account.balance}")
            
            # Apply cash to purchase
            old_paid = self.purchase.paid_amount
            self.purchase.paid_amount += cash_amount
            self.purchase.due_amount = max(Decimal('0.00'), self.purchase.grand_total - self.purchase.paid_amount)
            self.purchase._update_payment_status()
            
            # Update payment method and account for the purchase
            self.purchase.payment_method = self.payment_method
            self.purchase.account = self.account
            
            logger.info(f"💵 Cash applied to purchase: {cash_amount}, New paid: {self.purchase.paid_amount}")
            
            # Update account balance
            old_balance = self.account.balance
            self.account.balance -= cash_amount
            self.account.save(update_fields=['balance'])
            logger.info(f"🏦 Account balance updated: {old_balance} -> {self.account.balance}")
        
        # Save purchase updates
        update_fields = ['paid_amount', 'due_amount', 'payment_status', 'date_updated']
        if cash_amount > 0:
            update_fields.extend(['payment_method', 'account'])
        
        self.purchase.save(update_fields=update_fields)

    def _process_overall_payment(self):
        """Process overall payment across due purchases"""
        logger.info(f"🔄 Processing OVERALL payment for {self.supplier.name}, Amount: {self.amount}")
        
        # Refresh supplier to get latest data
        self.supplier.refresh_from_db()
        
        # Calculate cash amount
        advance_used = self.advance_amount_used if self.use_advance else Decimal('0.00')
        cash_amount = self.amount - advance_used
        
        # Use advance first if specified
        remaining_advance = advance_used
        if self.use_advance and remaining_advance > 0:
            remaining_advance = self._apply_advance_to_due_purchases(remaining_advance)
        
        # Use cash for remaining amount
        remaining_cash = cash_amount
        if remaining_cash > 0:
            remaining_cash = self._apply_cash_to_due_purchases(remaining_cash)
        
        # Handle any remaining amount as advance
        remaining_total = remaining_advance + remaining_cash
        if remaining_total > 0:
            logger.info(f"🎁 Converting remaining amount {remaining_total} to advance")
            
            old_advance = self.supplier.advance_balance
            self.supplier.advance_balance += remaining_total
            self.supplier.save(update_fields=['advance_balance', 'updated_at'])
            
            logger.info(f"✅ Added remaining to advance: {remaining_total}, Balance: {old_advance} -> {self.supplier.advance_balance}")

    def _apply_advance_to_due_purchases(self, advance_amount):
        """Apply advance amount to due purchases"""
        due_purchases = Purchase.objects.filter(
            supplier=self.supplier,
            company=self.company,
            due_amount__gt=0
        ).order_by('purchase_date')
        
        remaining = advance_amount
        
        for purchase in due_purchases:
            if remaining <= 0:
                break
                
            applied = min(remaining, purchase.due_amount)
            logger.info(f"💳 Applying advance {applied} to purchase {purchase.invoice_no}")
            
            purchase.paid_amount += applied
            purchase.due_amount = max(Decimal('0.00'), purchase.grand_total - purchase.paid_amount)
            purchase._update_payment_status()
            purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'date_updated'])
            
            remaining -= applied
        
        # Update supplier advance balance for actual amount used
        actual_used = advance_amount - remaining
        if actual_used > 0:
            old_advance = self.supplier.advance_balance
            self.supplier.advance_balance -= actual_used
            self.supplier.save(update_fields=['advance_balance', 'updated_at'])
            logger.info(f"💰 Advance used: {actual_used}, Balance: {old_advance} -> {self.supplier.advance_balance}")
        
        return remaining

    def _apply_cash_to_due_purchases(self, cash_amount):
        """Apply cash amount to due purchases"""
        if not self.account:
            raise ValueError("Account is required for cash payments")
            
        due_purchases = Purchase.objects.filter(
            supplier=self.supplier,
            company=self.company,
            due_amount__gt=0
        ).order_by('purchase_date')
        
        remaining = cash_amount
        
        for purchase in due_purchases:
            if remaining <= 0:
                break
                
            applied = min(remaining, purchase.due_amount)
            logger.info(f"💵 Applying cash {applied} to purchase {purchase.invoice_no}")
            
            purchase.paid_amount += applied
            purchase.due_amount = max(Decimal('0.00'), purchase.grand_total - purchase.paid_amount)
            purchase._update_payment_status()
            
            # Update payment method for purchases paid with cash
            purchase.payment_method = self.payment_method
            purchase.account = self.account
            
            purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'payment_method', 'account', 'date_updated'])
            
            remaining -= applied
        
        # Update account balance for actual cash used
        actual_used = cash_amount - remaining
        if actual_used > 0:
            old_balance = self.account.balance
            self.account.balance -= actual_used
            self.account.save(update_fields=['balance'])
            logger.info(f"🏦 Cash used: {actual_used}, Account balance: {old_balance} -> {self.account.balance}")
        
        return remaining

    def get_payment_summary(self):
        """Get comprehensive payment summary"""
        # Get the first transaction linked to this payment
        transaction = self.transactions.first() if hasattr(self, 'transactions') and self.transactions.exists() else None
        
        summary = {
            'payment_id': self.id,
            'sp_no': self.sp_no,
            'supplier': self.supplier.name,
            'payment_type': self.payment_type,
            'total_amount': float(self.amount),
            'advance_used': float(self.advance_amount_used),
            'cash_amount': float(self.amount - self.advance_amount_used),
            'payment_method': self.payment_method,
            'payment_date': self.payment_date.isoformat(),
            'status': self.status,
            'account': self.account.name if self.account else None,
            'transaction_no': transaction.transaction_no if transaction else None,
        }
        
        if self.payment_type == 'specific' and self.purchase:
            summary.update({
                'invoice_no': self.purchase.invoice_no,
                'invoice_total': float(self.purchase.grand_total),
            })
        
        return summary

    # ... rest of your methods ...

    def cancel_payment(self):
        """Cancel this payment and reverse all effects"""
        if self.status != 'completed':
            raise ValidationError("Only completed payments can be cancelled")
        
        with transaction.atomic():
            # Reverse the transaction first
            if self.transaction:
                self.transaction.reverse()
                logger.info(f"🔄 Transaction {self.transaction.transaction_no} reversed")
            
            # Reverse the payment effects based on type
            if self.payment_type == 'advance':
                self._reverse_advance_payment()
            elif self.payment_type == 'specific':
                self._reverse_specific_payment()
            else:  # overall
                self._reverse_overall_payment()
            
            # Update status
            self.status = 'cancelled'
            self.save(update_fields=['status', 'updated_at'])
            
            logger.info(f"🔄 Payment {self.sp_no} cancelled successfully")

    def _reverse_advance_payment(self):
        """Reverse advance payment effects"""
        # Decrease supplier advance balance (reverse the increase)
        old_advance = self.supplier.advance_balance
        self.supplier.advance_balance -= self.amount
        self.supplier.save(update_fields=['advance_balance', 'updated_at'])
        
        # Increase account balance if account was used (reverse the decrease)
        if self.account:
            old_balance = self.account.balance
            self.account.balance += self.amount
            self.account.save(update_fields=['balance'])
            
            logger.info(f"🔄 Reversed advance payment: Supplier advance {old_advance} -> {self.supplier.advance_balance}, Account {old_balance} -> {self.account.balance}")

    @classmethod
    def get_supplier_payment_summary(cls, supplier, company):
        """Get payment summary for a supplier"""
        payments = cls.objects.filter(supplier=supplier, company=company, status='completed')
        
        total_payments = payments.aggregate(
            total_amount=models.Sum('amount'),
            total_advance_used=models.Sum('advance_amount_used')
        )
        
        return {
            'total_payments': float(total_payments['total_amount'] or 0),
            'total_advance_used': float(total_payments['total_advance_used'] or 0),
            'total_cash_payments': float((total_payments['total_amount'] or 0) - (total_payments['total_advance_used'] or 0)),
            'payment_count': payments.count(),
            'current_advance_balance': float(supplier.advance_balance)
        }