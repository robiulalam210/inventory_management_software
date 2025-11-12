from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Account
from products.models import Product
from core.models import Company
from customers.models import Customer
from django.utils import timezone
from django.conf import settings
from decimal import Decimal

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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_paid_amount = 0
        
        if not is_new:
            try:
                old_instance = Sale.objects.get(pk=self.pk)
                old_paid_amount = old_instance.paid_amount
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
            raise ValueError("Saved customer must have a customer record.")
        
        # Generate invoice number for new sales
        if is_new and not self.invoice_no:
            last_receipt = Sale.objects.filter(company=self.company).order_by("-id").first()
            new_id = (last_receipt.id + 1) if last_receipt else 1
            self.invoice_no = f"SL-{1000 + new_id}"
        
        # Save first
        super().save(*args, **kwargs)
        
        # Update totals after saving
        self.update_totals()
        
        # Check if payment was made and create receipt
        payment_increased = not is_new and self.paid_amount > old_paid_amount
        if payment_increased and self.with_money_receipt == 'Yes':
            self.create_money_receipt()

    def update_totals(self):
        items = self.items.all()
        gross = sum([item.subtotal() for item in items])

        # Calculate overall discount
        discount_amount = Decimal('0.00')
        if self.overall_discount_type == 'percent':
            discount_amount = gross * (self.overall_discount / Decimal('100.00'))
        elif self.overall_discount_type == 'fixed':
            discount_amount = self.overall_discount

        # Calculate charges on GROSS amount
        vat_amount = Decimal('0.00')
        if self.overall_vat_type == 'percent':
            vat_amount = gross * (self.overall_vat_amount / Decimal('100.00'))
        elif self.overall_vat_type == 'fixed':
            vat_amount = self.overall_vat_amount

        service_amount = Decimal('0.00')
        if self.overall_service_type == 'percent':
            service_amount = gross * (self.overall_service_charge / Decimal('100.00'))
        elif self.overall_service_type == 'fixed':
            service_amount = self.overall_service_charge

        delivery_amount = Decimal('0.00')
        if self.overall_delivery_type == 'percent':
            delivery_amount = gross * (self.overall_delivery_charge / Decimal('100.00'))
        elif self.overall_delivery_type == 'fixed':
            delivery_amount = self.overall_delivery_charge

        # Calculate NET TOTAL (without delivery charge)
        net_total = gross - discount_amount + vat_amount + service_amount
        
        # Calculate GRAND TOTAL (net total + delivery charge)
        grand_total = net_total + delivery_amount

        self.gross_total = round(gross, 2)
        self.net_total = round(net_total, 2)
        self.grand_total = round(grand_total, 2)
        self.payable_amount = round(grand_total, 2)
        
        # CALCULATE CHANGE AMOUNT (overpayment)
        self.change_amount = max(Decimal('0.00'), self.paid_amount - self.payable_amount)
        
        # Calculate due amount (0 if overpaid)
        self.due_amount = max(Decimal('0.00'), self.payable_amount - self.paid_amount)
        
        # ✅ FIXED: Update payment status - ALLOW PARTIAL PAYMENTS FOR ALL CUSTOMERS
        if self.paid_amount >= self.payable_amount:
            self.due_amount = Decimal('0.00')
            self.payment_status = 'paid'
            if self.change_amount > 0:
                print(f"💵 Change to return: {self.change_amount}")
        elif self.paid_amount > Decimal('0.00') and self.paid_amount < self.payable_amount:
            self.payment_status = 'partial'  # This is now allowed for ALL customers
        else:
            self.payment_status = 'pending'

        super().save(update_fields=[
            "gross_total", "net_total", "grand_total", 
            "payable_amount", "due_amount", "change_amount",
            "payment_status"
        ])
        
        # Auto-create money receipt when payment is made
        if (self.paid_amount > Decimal('0.00') and 
            self.with_money_receipt == 'Yes' and
            self.payment_status in ['paid', 'partial']):
            self.create_money_receipt()

    def create_money_receipt(self):
        """
        Automatically create money receipt when payment is made
        """
        # Don't create receipt if no payment
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
            
            # Allow creation even without customer
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
            
            money_receipt.save()
            print(f"Money receipt created automatically: {money_receipt.mr_no} for {self.invoice_no}")
            return money_receipt
            
        except Exception as e:
            print(f"Error creating money receipt: {e}")
            return None

    def clean(self):
        """Model validation - REMOVED strict walk-in validation"""
        super().clean()
        
        # ✅ FIXED: Remove the strict validation for walk-in customers
        # Allow partial payments for walk-in customers
        if self.customer_type == 'walk_in':
            # Only validate that due_amount is not negative
            if self.due_amount < 0:
                raise ValidationError({
                    'due_amount': 'Due amount cannot be negative.'
                })
            # REMOVED: The strict paid_amount >= payable_amount validation
        
        # Keep saved customer validation
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError({
                'customer': 'Saved customer must have a customer record.'
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
        
        self.paid_amount += amount
        
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
            
        self.save()
        
        # Update account balance
        if account and amount > 0:
            account.balance += amount
            account.save(update_fields=['balance'])
            
        return self.paid_amount


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), null=True, blank=True)

    def subtotal(self):
        total = self.unit_price * self.quantity
        
        if self.discount_type == 'percent' and self.discount:
            total -= total * (self.discount / 100)
        elif self.discount_type == 'fixed' and self.discount:
            total -= self.discount
            
        return round(total, 2)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValueError(f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}")
        
        super().save(*args, **kwargs)

        if is_new:
            self.product.stock_qty -= self.quantity
            self.product.save(update_fields=['stock_qty'])
        
        self.sale.update_totals()

    def delete(self, *args, **kwargs):
        self.product.stock_qty += self.quantity
        self.product.save(update_fields=['stock_qty'])
        
        sale = self.sale
        super().delete(*args, **kwargs)
        sale.update_totals()

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"