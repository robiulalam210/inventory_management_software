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

# Create a clean supplier_payment/models.py
from django.utils.translation import gettext_lazy as _


class SupplierPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        BANK = 'bank', _('Bank Transfer')
        CHEQUE = 'cheque', _('Cheque')
        MOBILE = 'mobile', _('Mobile Banking')
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    # Basic information
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE)
    
    # Payment details
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Metadata
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Supplier Payment')
        verbose_name_plural = _('Supplier Payments')
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Supplier Payment #{self.id} - {self.supplier.name} - ৳{self.amount}"


    def clean(self):
        """Validate payment data"""
        errors = {}
        
        # Validate payment type consistency
        if self.payment_type == 'specific' and not self.purchase:
            errors['purchase'] = 'Purchase must be selected for specific bill payments'
        
        if self.payment_type == 'advance' and self.purchase:
            errors['purchase'] = 'Purchase should not be selected for advance payments'
        
        # Validate advance usage
        if self.use_advance:
            if self.advance_amount_used > self.supplier.advance_balance:
                errors['advance_amount_used'] = f'Advance amount used ({self.advance_amount_used}) exceeds available advance balance ({self.supplier.advance_balance})'
            
            if self.advance_amount_used > self.amount:
                errors['advance_amount_used'] = 'Advance amount used cannot be greater than total payment amount'
        
        # Validate account balance for non-advance portion
        if self.account and not self.use_advance and self.amount > self.account.balance:
            errors['amount'] = f'Insufficient balance in account {self.account.name}'
        
        if self.account and self.use_advance:
            cash_amount = self.amount - self.advance_amount_used
            if cash_amount > self.account.balance:
                errors['amount'] = f'Insufficient balance in account {self.account.name} for cash portion'
        
        if errors:
            raise ValidationError(errors)

    def generate_sp_no(self):
        """Generate unique supplier payment number"""
        try:
            last_payment = SupplierPayment.objects.filter(
                company=self.company
            ).order_by('-sp_no').first()
            
            if last_payment and last_payment.sp_no:
                try:
                    last_number = int(last_payment.sp_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1001
            else:
                new_number = 1001
                
            return f"SP-{new_number}"
        except Exception as e:
            logger.error(f"Error generating SP number: {e}")
            return f"SP-1001"

    def save(self, *args, **kwargs):
        """Save with proper validation and payment processing - COMPLETELY FIXED"""
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
            
            # Process payment if new
            if is_new:
                logger.info(f"🆕 NEW PAYMENT DETECTED: {self.sp_no}")
                self._process_payment()

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
            raise

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
        
        # Calculate amounts
        advance_used = self.advance_amount_used if self.use_advance else Decimal('0.00')
        cash_amount = self.amount - advance_used
        
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
        """Process overall payment across due purchases - COMPLETELY REWRITTEN"""
        logger.info(f"🔄 Processing OVERALL payment for {self.supplier.name}, Amount: {self.amount}")
        
        # Refresh supplier to get latest data
        self.supplier.refresh_from_db()
        logger.info(f"📊 Supplier BEFORE - Advance: {self.supplier.advance_balance}")
        
        # Get due purchases
        due_purchases = Purchase.objects.filter(
            supplier=self.supplier,
            company=self.company,
            due_amount__gt=0
        ).order_by('purchase_date')
        
        logger.info(f"📊 Due purchases found: {due_purchases.count()}")
        
        # If no due purchases, ENTIRE payment becomes advance
        if due_purchases.count() == 0:
            logger.info(f"🎯 NO DUE PURCHASES - Converting entire payment to advance")
            
            old_advance = self.supplier.advance_balance
            self.supplier.advance_balance += self.amount
            self.supplier.save(update_fields=['advance_balance', 'updated_at'])
            
            logger.info(f"✅ Advance balance updated: {old_advance} -> {self.supplier.advance_balance}")
            
            # Update account balance
            if self.account:
                old_balance = self.account.balance
                self.account.balance -= self.amount
                self.account.save(update_fields=['balance'])
                logger.info(f"🏦 Account balance updated: {old_balance} -> {self.account.balance}")
            
            return
        
        # If there are due purchases, apply payment to them
        remaining_amount = self.amount
        
        # Use advance first if specified
        if self.use_advance and self.advance_amount_used > 0:
            advance_remaining = self.advance_amount_used
            
            for purchase in due_purchases:
                if advance_remaining <= 0:
                    break
                    
                applied = min(advance_remaining, purchase.due_amount)
                logger.info(f"💳 Applying advance {applied} to purchase {purchase.invoice_no}")
                
                purchase.paid_amount += applied
                purchase.due_amount = max(Decimal('0.00'), purchase.grand_total - purchase.paid_amount)
                purchase._update_payment_status()
                purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'date_updated'])
                
                advance_remaining -= applied
                remaining_amount -= applied
            
            # Update supplier advance balance
            actual_advance_used = self.advance_amount_used - advance_remaining
            if actual_advance_used > 0:
                old_advance = self.supplier.advance_balance
                self.supplier.advance_balance -= actual_advance_used
                self.supplier.save(update_fields=['advance_balance', 'updated_at'])
                logger.info(f"💰 Advance used: {actual_advance_used}, Balance: {old_advance} -> {self.supplier.advance_balance}")
        
        # Use cash for remaining amount
        cash_amount = self.amount - (self.advance_amount_used if self.use_advance else Decimal('0.00'))
        
        if cash_amount > 0 and remaining_amount > 0:
            if not self.account:
                raise ValueError("Account is required for cash payments")
            
            cash_remaining = cash_amount
            
            for purchase in due_purchases:
                if cash_remaining <= 0:
                    break
                    
                # Skip if purchase is already paid
                current_due = purchase.due_amount
                if current_due <= 0:
                    continue
                
                applied = min(cash_remaining, current_due)
                logger.info(f"💵 Applying cash {applied} to purchase {purchase.invoice_no}")
                
                purchase.paid_amount += applied
                purchase.due_amount = max(Decimal('0.00'), purchase.grand_total - purchase.paid_amount)
                purchase._update_payment_status()
                
                # Update payment method for purchases paid with cash
                if applied == current_due:
                    purchase.payment_method = self.payment_method
                    purchase.account = self.account
                
                purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'payment_method', 'account', 'date_updated'])
                
                cash_remaining -= applied
                remaining_amount -= applied
            
            # Update account balance for actual cash used
            actual_cash_used = cash_amount - cash_remaining
            if actual_cash_used > 0:
                old_balance = self.account.balance
                self.account.balance -= actual_cash_used
                self.account.save(update_fields=['balance'])
                logger.info(f"🏦 Cash used: {actual_cash_used}, Account balance: {old_balance} -> {self.account.balance}")
        
        # Handle any remaining amount as advance
        if remaining_amount > 0:
            logger.info(f"🎁 Converting remaining amount {remaining_amount} to advance")
            
            old_advance = self.supplier.advance_balance
            self.supplier.advance_balance += remaining_amount
            self.supplier.save(update_fields=['advance_balance', 'updated_at'])
            
            logger.info(f"✅ Added remaining to advance: {remaining_amount}, Balance: {old_advance} -> {self.supplier.advance_balance}")
        
        # Log final state
        self.supplier.refresh_from_db()
        logger.info(f"📊 Supplier AFTER - Advance: {self.supplier.advance_balance}")

    def get_payment_summary(self):
        """Get comprehensive payment summary"""
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
            'affected_invoices': self.get_affected_invoices(),
        }
        
        if self.payment_type == 'specific' and self.purchase:
            summary.update({
                'invoice_no': self.purchase.invoice_no,
                'invoice_total': float(self.purchase.grand_total),
                'paid_before': float(self.purchase.paid_amount - (self.amount - self.advance_amount_used)),
                'paid_after': float(self.purchase.paid_amount),
                'due_before': float(self.purchase.due_amount + (self.amount - self.advance_amount_used)),
                'due_after': float(self.purchase.due_amount),
            })
        
        return summary

    def get_affected_invoices(self):
        """Get list of invoices affected by this payment"""
        affected = []
        
        if self.payment_type == 'specific' and self.purchase:
            affected.append({
                'invoice_no': self.purchase.invoice_no,
                'amount_applied': float(self.amount),
                'advance_used': float(self.advance_amount_used),
                'cash_applied': float(self.amount - self.advance_amount_used)
            })
        elif self.payment_type == 'overall':
            # Get all purchases for this supplier
            purchases = Purchase.objects.filter(
                supplier=self.supplier,
                company=self.company
            )
            
            for purchase in purchases:
                affected.append({
                    'invoice_no': purchase.invoice_no,
                    'current_due': float(purchase.due_amount),
                    'grand_total': float(purchase.grand_total),
                    'paid_amount': float(purchase.paid_amount)
                })
        
        return affected

    @classmethod
    def get_supplier_payment_summary(cls, supplier, company):
        """Get payment summary for a supplier"""
        payments = cls.objects.filter(supplier=supplier, company=company)
        
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