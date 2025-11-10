# supplier_payment/models.py
from django.db import models
from core.models import Company
from suppliers.models import Supplier
from purchases.models import Purchase  # ✅ Fixed import
from accounts.models import Account
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class SupplierPayment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('overall', 'Overall Payment'),
        ('specific', 'Specific Bill Payment'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('digital', 'Digital Payment'),
    ]

    CHEQUE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('cleared', 'Cleared'),
        ('bounced', 'Bounced'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    sp_no = models.CharField(max_length=20, )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    purchase = models.ForeignKey(Purchase, on_delete=models.SET_NULL, null=True, blank=True)  # ✅ Fixed: removed quotes

    # Payment type fields
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='overall')
    specific_bill = models.BooleanField(default=False)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_date = models.DateTimeField(default=timezone.now)
    remark = models.TextField(null=True, blank=True)
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Cheque related fields
    cheque_status = models.CharField(max_length=20, choices=CHEQUE_STATUS_CHOICES, null=True, blank=True)
    cheque_no = models.CharField(max_length=64, null=True, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Supplier Payment'
        verbose_name_plural = 'Supplier Payments'

    def __str__(self):
        return f"{self.sp_no} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Generate SP number if new
        if is_new and not self.sp_no:
            last_payment = SupplierPayment.objects.filter(company=self.company).order_by("-id").first()
            new_id = (last_payment.id + 1) if last_payment else 1
            self.sp_no = f"SP-{1000 + new_id}"

        # Set payment type based on purchase
        if self.purchase:
            self.payment_type = 'specific'
            self.specific_bill = True
        else:
            self.payment_type = 'overall'
            self.specific_bill = False

        super().save(*args, **kwargs)

        # Process payment automatically if manual
        if is_new and not getattr(self, '_auto_created', False):
            self.process_payment()

    def process_payment(self):
        """
        Process supplier payment based on type
        """
        try:
            if self.payment_type == 'specific' and self.purchase:
                self._process_specific_bill_payment()
            else:
                self._process_overall_payment()
        except Exception as e:
            print(f"Supplier payment processing error: {e}")

    def _process_specific_bill_payment(self):
        """
        Process payment for a specific purchase bill
        """
        if not self.purchase:
            return False

        purchase = self.purchase

        if self.amount > purchase.due_amount:
            raise ValueError(
                f"Payment amount ({self.amount}) cannot be greater than due amount ({purchase.due_amount})"
            )

        # Update purchase safely using ORM
        purchase.paid_amount += self.amount
        purchase.due_amount = max(purchase.due_amount - self.amount, 0)
        purchase.payment_status = 'paid' if purchase.due_amount == 0 else 'partial'
        purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])

        print(f"Payment processed for purchase {purchase.invoice_no}: {self.amount} Taka")  # ✅ Changed bill_no to invoice_no
        return True

    def _process_overall_payment(self):
        """
        Process payment for all due purchases of the supplier
        """
        due_purchases = Purchase.objects.filter(
            supplier=self.supplier,
            company=self.company,
            due_amount__gt=0
        ).order_by('purchase_date')

        remaining = self.amount
        for purchase in due_purchases:
            if remaining <= 0:
                break

            applied = min(remaining, purchase.due_amount)
            purchase.paid_amount += applied
            purchase.due_amount = max(purchase.due_amount - applied, 0)
            purchase.payment_status = 'paid' if purchase.due_amount == 0 else 'partial'
            purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
            print(f"Payment applied to purchase {purchase.invoice_no}: {applied} Taka")  # ✅ Changed bill_no to invoice_no

            remaining -= applied

        return True

    def get_payment_summary(self):
        """
        Returns a dictionary summary of the supplier payment
        """
        if self.payment_type == 'specific' and self.purchase:
            purchase = self.purchase
            previous_paid = float(purchase.paid_amount - self.amount)
            previous_due = float(purchase.due_amount + self.amount)

            return {
                'payment_type': 'specific_bill',
                'invoice_no': purchase.invoice_no,  # ✅ Changed bill_no to invoice_no
                'before_payment': {
                    'invoice_total': float(purchase.grand_total),
                    'previous_paid': previous_paid,
                    'previous_due': previous_due,
                },
                'after_payment': {
                    'current_paid': float(purchase.paid_amount),
                    'current_due': float(purchase.due_amount),
                    'payment_applied': float(self.amount),
                },
                'status': 'completed' if purchase.due_amount == 0 else 'partial'
            }

        else:
            from django.db.models import Sum

            total_due_before = Purchase.objects.filter(
                supplier=self.supplier,
                company=self.company,
                due_amount__gt=0
            ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0

            total_due_after = max(total_due_before - self.amount, 0)

            return {
                'payment_type': 'overall',
                'before_payment': {'total_due': float(total_due_before)},
                'after_payment': {
                    'total_due': float(total_due_after),
                    'payment_applied': float(self.amount)
                },
                'affected_invoices': self.get_affected_invoices(),  # ✅ Changed method name
                'status': 'completed' if total_due_after == 0 else 'partial'
            }

    def get_affected_invoices(self):  # ✅ Changed method name
        """
        Returns list of purchase invoices affected by this payment
        """
        affected = []
        remaining = self.amount

        if self.payment_type == 'specific' and self.purchase:
            affected.append({
                'invoice_no': self.purchase.invoice_no,  # ✅ Changed bill_no to invoice_no
                'amount_applied': float(self.amount)
            })
        else:
            due_purchases = Purchase.objects.filter(
                supplier=self.supplier,
                company=self.company,
                due_amount__gt=0
            ).order_by('purchase_date')

            for purchase in due_purchases:
                if remaining <= 0:
                    break

                applied = min(remaining, purchase.due_amount)
                affected.append({
                    'invoice_no': purchase.invoice_no,  # ✅ Changed bill_no to invoice_no
                    'amount_applied': float(applied)
                })
                remaining -= applied

        return affected

    @classmethod
    def create_auto_payment(cls, purchase):
        """
        Create a SupplierPayment automatically without processing payment
        """
        payment = cls(
            company=purchase.company,
            supplier=purchase.supplier,
            purchase=purchase,
            payment_type='specific',
            specific_bill=True,
            amount=purchase.paid_amount,
            payment_method=purchase.payment_method or 'Cash',
            payment_date=timezone.now(),
            remark=f"Auto-generated payment - {purchase.invoice_no}",  # ✅ Changed bill_no to invoice_no
            prepared_by=purchase.created_by,  # ✅ Changed to created_by
            account=purchase.account,
        )

        setattr(payment, '_auto_created', True)
        payment.save()
        return payment

    def get_cheque_status_display(self):
        """
        Get human-readable cheque status
        """
        if self.payment_method == 'cheque' and self.cheque_status:
            return dict(self.CHEQUE_STATUS_CHOICES).get(self.cheque_status, 'N/A')
        return 'N/A'