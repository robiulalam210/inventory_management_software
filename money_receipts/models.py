from django.db import models
from core.models import Company
from customers.models import Customer
from accounts.models import Account
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class MoneyReceipt(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('overall', 'Overall Payment'),
        ('specific', 'Specific Invoice Payment'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mr_no = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)

    # Payment type fields
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='overall')
    specific_invoice = models.BooleanField(default=False)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100)
    payment_date = models.DateTimeField()
    remark = models.TextField(null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_status = models.CharField(max_length=20, null=True, blank=True)
    cheque_id = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mr_no} - {self.customer.name if self.customer else 'N/A'}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Generate MR number if new
        if is_new and not self.mr_no:
            last_receipt = MoneyReceipt.objects.filter(company=self.company).order_by("-id").first()
            new_id = (last_receipt.id + 1) if last_receipt else 1
            self.mr_no = f"MR-{1000 + new_id}"

        # Set payment type
        if self.sale:
            self.payment_type = 'specific'
            self.specific_invoice = True
        else:
            self.payment_type = 'overall'
            self.specific_invoice = False

        super().save(*args, **kwargs)

        # Process payment automatically if manual
        if is_new and not getattr(self, '_auto_created', False):
            self.process_payment()

    def process_payment(self):
        """
        Process payment based on type
        """
        try:
            if self.payment_type == 'specific' and self.sale:
                self._process_specific_invoice_payment()
            else:
                self._process_overall_payment()
        except Exception as e:
            print(f"Payment processing error: {e}")

    def _process_specific_invoice_payment(self):
        """
        Process payment for a specific invoice
        """
        if not self.sale:
            return False

        if self.amount > self.sale.due_amount:
            raise ValueError(
                f"Payment amount ({self.amount}) cannot be greater than due amount ({self.sale.due_amount})"
            )

        # Update sale safely using ORM
        sale = self.sale
        sale.paid_amount += self.amount
        sale.due_amount = max(sale.due_amount - self.amount, 0)
        sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
        sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])

        print(f"Payment processed for invoice {sale.invoice_no}: {self.amount} Taka")
        return True

    def _process_overall_payment(self):
        """
        Process payment for all due invoices of the customer
        """
        from sales.models import Sale

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
            sale.paid_amount += applied
            sale.due_amount = max(sale.due_amount - applied, 0)
            sale.payment_status = 'paid' if sale.due_amount == 0 else 'partial'
            sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
            print(f"Payment applied to invoice {sale.invoice_no}: {applied} Taka")

            remaining -= applied

        return True

    def get_payment_summary(self):
        """
        Returns a dictionary summary of the payment
        """
        if self.payment_type == 'specific' and self.sale:
            sale = self.sale
            previous_paid = float(sale.paid_amount - self.amount)
            previous_due = float(sale.due_amount + self.amount)

            return {
                'payment_type': 'specific_invoice',
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
                'status': 'completed' if sale.due_amount == 0 else 'partial'
            }

        else:
            from sales.models import Sale
            from django.db.models import Sum

            total_due_before = Sale.objects.filter(
                customer=self.customer,
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
                'affected_invoices': self.get_affected_invoices(),
                'status': 'completed' if total_due_after == 0 else 'partial'
            }

    def get_affected_invoices(self):
        """
        Returns list of invoices affected by this receipt
        """
        from sales.models import Sale

        affected = []
        remaining = self.amount

        if self.payment_type == 'specific' and self.sale:
            affected.append({
                'invoice_no': self.sale.invoice_no,
                'amount_applied': float(self.amount)
            })
        else:
            due_sales = Sale.objects.filter(
                customer=self.customer,
                company=self.company,
                due_amount__gt=0
            ).order_by('sale_date')

            for sale in due_sales:
                if remaining <= 0:
                    break

                applied = min(remaining, sale.due_amount)
                affected.append({
                    'invoice_no': sale.invoice_no,
                    'amount_applied': float(applied)
                })
                remaining -= applied

        return affected

    @classmethod
    def create_auto_receipt(cls, sale):
        """
        Create a MoneyReceipt automatically without processing payment
        """
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
        )

        setattr(receipt, '_auto_created', True)
        receipt.save()
        return receipt
