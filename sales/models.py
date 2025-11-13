from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Account
from products.models import Product
from core.models import Company
from customers.models import Customer
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]
    CUSTOMER_TYPE_CHOICES = [('walk_in', 'Walk-in'), ('saved_customer', 'Saved Customer')]
    MONEY_RECEIPT_CHOICES = [('Yes', 'Yes'), ('No', 'No')]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_created')
    sale_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_made')

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)

    customer_name = models.CharField(max_length=100, blank=True, null=True)

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    invoice_no = models.CharField(max_length=20, blank=True, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='walk_in')
    with_money_receipt = models.CharField(max_length=3, choices=MONEY_RECEIPT_CHOICES, default='No')
    remark = models.TextField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    overall_vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='sales')

    class Meta:
        ordering = ['-sale_date', '-id']
        indexes = [
            models.Index(fields=['company', 'sale_date']),
            models.Index(fields=['customer', 'sale_date']),
            models.Index(fields=['invoice_no']),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_paid_amount = 0
        
        if not is_new:
            try:
                old_instance = Sale.objects.get(pk=self.pk)
                old_paid_amount = old_instance.paid_amount
                # Store old values for signal processing
                self._old_paid_amount = old_paid_amount
            except Sale.DoesNotExist:
                pass
        
        # Handle customer_name for walk-in customers
        if self.customer_type == 'walk_in' and not self.customer_name:
            self.customer_name = 'Walk-in Customer'
        
        # For walk-in customers without customer_id, use customer_name directly
        if self.customer_type == 'walk_in' and not self.customer:
            if self.customer_name and self.customer_name != 'Walk-in Customer':
                pass
            else:
                self.customer_name = 'Walk-in Customer'
        
        # For saved customers, ensure customer is set
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError("Saved customer must have a customer record.")
        
        # Generate invoice number for new sales
        if is_new and not self.invoice_no:
            self.invoice_no = self._generate_invoice_no()
        
        # Save first to get PK for related objects
        super().save(*args, **kwargs)
        
        # Update totals after saving
        self.update_totals()
        
        # Check if payment was made and create receipt
        payment_increased = not is_new and self.paid_amount > old_paid_amount
        if payment_increased and self.with_money_receipt == 'Yes':
            self.create_money_receipt()

    def _generate_invoice_no(self):
        """Generate unique invoice number"""
        if not self.company:
            return None
            
        last_sale = Sale.objects.filter(company=self.company).order_by("-id").first()
        new_id = (last_sale.id + 1) if last_sale else 1
        return f"SL-{1000 + new_id}"

    def update_totals(self):
        """Update all calculated totals for the sale"""
        try:
            items = self.items.all()
            gross = sum([item.subtotal() for item in items]) if items.exists() else Decimal('0.00')

            # Calculate overall discount
            discount_amount = Decimal('0.00')
            if self.overall_discount_type == 'percent' and self.overall_discount:
                discount_amount = gross * (self.overall_discount / Decimal('100.00'))
            elif self.overall_discount_type == 'fixed' and self.overall_discount:
                discount_amount = self.overall_discount

            # Calculate charges on GROSS amount
            vat_amount = Decimal('0.00')
            if self.overall_vat_type == 'percent' and self.overall_vat_amount:
                vat_amount = gross * (self.overall_vat_amount / Decimal('100.00'))
            elif self.overall_vat_type == 'fixed' and self.overall_vat_amount:
                vat_amount = self.overall_vat_amount

            service_amount = Decimal('0.00')
            if self.overall_service_type == 'percent' and self.overall_service_charge:
                service_amount = gross * (self.overall_service_charge / Decimal('100.00'))
            elif self.overall_service_type == 'fixed' and self.overall_service_charge:
                service_amount = self.overall_service_charge

            delivery_amount = Decimal('0.00')
            if self.overall_delivery_type == 'percent' and self.overall_delivery_charge:
                delivery_amount = gross * (self.overall_delivery_charge / Decimal('100.00'))
            elif self.overall_delivery_type == 'fixed' and self.overall_delivery_charge:
                delivery_amount = self.overall_delivery_charge

            # Calculate NET TOTAL (without delivery charge)
            net_total = gross - discount_amount + vat_amount + service_amount
            
            # Calculate GRAND TOTAL (net total + delivery charge)
            grand_total = net_total + delivery_amount

            # Update fields
            self.gross_total = round(gross, 2)
            self.net_total = round(net_total, 2)
            self.grand_total = round(grand_total, 2)
            self.payable_amount = round(grand_total, 2)
            
            # CALCULATE CHANGE AMOUNT (overpayment)
            self.change_amount = max(Decimal('0.00'), self.paid_amount - self.payable_amount)
            
            # Calculate due amount (0 if overpaid)
            self.due_amount = max(Decimal('0.00'), self.payable_amount - self.paid_amount)
            
            # Update payment status
            self._update_payment_status()

            # Save the updated totals
            super().save(update_fields=[
                "gross_total", "net_total", "grand_total", 
                "payable_amount", "due_amount", "change_amount",
                "payment_status"
            ])
            
        except Exception as e:
            logger.error(f"Error updating totals for sale {self.invoice_no}: {str(e)}")

    def _update_payment_status(self):
        """Update payment status based on current amounts"""
        if self.paid_amount >= self.payable_amount:
            self.due_amount = Decimal('0.00')
            self.payment_status = 'paid'
            if self.change_amount > 0:
                logger.info(f"Change to return: {self.change_amount} for sale {self.invoice_no}")
        elif self.paid_amount > Decimal('0.00') and self.paid_amount < self.payable_amount:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'

    def create_money_receipt(self):
        """
        Automatically create money receipt when payment is made
        """
        if self.paid_amount <= 0:
            return None
        
        try:
            from money_receipts.models import MoneyReceipt
            
            # Check if money receipt already exists for this sale
            existing_receipt = MoneyReceipt.objects.filter(sale=self).first()
            
            if existing_receipt:
                if existing_receipt.amount != self.paid_amount:
                    existing_receipt.amount = self.paid_amount
                    existing_receipt.save()
                return existing_receipt
            
            # Create new money receipt
            money_receipt = MoneyReceipt(
                company=self.company,
                customer=self.customer,
                sale=self,
                amount=self.paid_amount,
                payment_method=self.payment_method or 'Cash',
                payment_date=timezone.now(),
                remark=f"Auto-generated receipt for {self.invoice_no} - {self.get_customer_display()}",
                seller=self.sale_by,
                account=self.account
            )
            
            # Mark as auto-created to avoid recursion
            setattr(money_receipt, '_auto_created', True)
            money_receipt.save()
            
            logger.info(f"Money receipt created automatically: {money_receipt.mr_no} for {self.invoice_no}")
            return money_receipt
            
        except Exception as e:
            logger.error(f"Error creating money receipt for sale {self.invoice_no}: {e}")
            return None

    def clean(self):
        """Model validation"""
        super().clean()
        
        # Validate that due_amount is not negative
        if self.due_amount < 0:
            raise ValidationError({
                'due_amount': 'Due amount cannot be negative.'
            })
        
        # Validate saved customer has customer record
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError({
                'customer': 'Saved customer must have a customer record.'
            })
        
        # Validate payment method when payment is made
        if self.paid_amount > 0 and not self.payment_method:
            raise ValidationError({
                'payment_method': 'Payment method is required when payment is made.'
            })

    def __str__(self):
        return f"{self.invoice_no} - {self.get_customer_display()} - {self.get_customer_type_display()}"

    @property
    def is_walk_in_customer(self):
        return self.customer_type == 'walk_in'

    def get_customer_display(self):
        if self.customer_type == 'walk_in':
            return self.customer_name or "Walk-in Customer"
        return self.customer.name if self.customer else "Unknown Customer"

    def add_payment(self, amount, payment_method=None, account=None):
        """
        Add additional payment to existing sale
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
            
        self.paid_amount += amount
        self.save()
        
        return self.paid_amount

    def get_payment_summary(self):
        """Get payment summary for the sale"""
        return {
            'invoice_no': self.invoice_no,
            'grand_total': float(self.grand_total),
            'paid_amount': float(self.paid_amount),
            'due_amount': float(self.due_amount),
            'change_amount': float(self.change_amount),
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
        }

    def can_add_payment(self):
        """Check if additional payment can be added"""
        return self.due_amount > 0 and self.payment_status in ['pending', 'partial']

    @classmethod
    def get_sales_summary(cls, company, start_date=None, end_date=None):
        """Get sales summary for a company"""
        queryset = cls.objects.filter(company=company)
        
        if start_date:
            queryset = queryset.filter(sale_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(sale_date__lte=end_date)
            
        return queryset.aggregate(
            total_sales=models.Count('id'),
            total_amount=models.Sum('grand_total'),
            total_paid=models.Sum('paid_amount'),
            total_due=models.Sum('due_amount')
        )


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), null=True, blank=True)

    class Meta:
        ordering = ['id']

    def subtotal(self):
        """Calculate subtotal for this item"""
        total = self.unit_price * self.quantity
        
        if self.discount_type == 'percent' and self.discount:
            total -= total * (self.discount / Decimal('100.00'))
        elif self.discount_type == 'fixed' and self.discount:
            total -= self.discount
            
        return round(max(total, Decimal('0.00')), 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Validate stock for new items
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}, Requested: {self.quantity}"
                )
        
        super().save(*args, **kwargs)

        # Update product stock for new items
        if is_new:
            self.product.stock_qty -= self.quantity
            self.product.save(update_fields=['stock_qty'])
        
        # Update sale totals
        self.sale.update_totals()

    def delete(self, *args, **kwargs):
        # Restore product stock
        self.product.stock_qty += self.quantity
        self.product.save(update_fields=['stock_qty'])
        
        sale = self.sale
        super().delete(*args, **kwargs)
        
        # Update sale totals after deletion
        sale.update_totals()

    def __str__(self):
        return f"{self.product.name} x {self.quantity} - {self.subtotal()}"

    def get_item_summary(self):
        """Get item summary"""
        return {
            'product': self.product.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'discount': float(self.discount),
            'discount_type': self.discount_type,
            'subtotal': float(self.subtotal())
        }