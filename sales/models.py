from django.db import models
from accounts.models import Account
from products.models import Product
from core.models import Company
from customers.models import Customer

class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]
    CUSTOMER_TYPE_CHOICES = [('walk_in', 'Walk-in'), ('saved_customer', 'Saved Customer')]
    MONEY_RECEIPT_CHOICES = [('Yes', 'Yes'), ('No', 'No')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    invoice_no = models.CharField(max_length=20, blank=True, null=True, unique=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    
    sale_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_made')
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='walk_in')
    with_money_receipt = models.CharField(max_length=3, choices=MONEY_RECEIPT_CHOICES, default='No')
    remark = models.TextField(blank=True, null=True)

    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # New field

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
        super().save(*args, **kwargs)

        if is_new and not self.invoice_no:
            self.invoice_no = f"PS-{1000 + self.id}"
            super().save(update_fields=["invoice_no"])

    def update_totals(self):
        items = self.items.all()
        gross = sum([item.subtotal() for item in items])

        # Calculate overall discount
        discount_amount = 0
        if self.overall_discount_type == 'percent':
            discount_amount = gross * (self.overall_discount / 100)
        elif self.overall_discount_type == 'fixed':
            discount_amount = self.overall_discount

        # Calculate charges on GROSS amount
        vat_amount = 0
        if self.overall_vat_type == 'percent':
            vat_amount = gross * (self.overall_vat_amount / 100)
        elif self.overall_vat_type == 'fixed':
            vat_amount = self.overall_vat_amount

        service_amount = 0
        if self.overall_service_type == 'percent':
            service_amount = gross * (self.overall_service_charge / 100)
        elif self.overall_service_type == 'fixed':
            service_amount = self.overall_service_charge

        delivery_amount = 0
        if self.overall_delivery_type == 'percent':
            delivery_amount = gross * (self.overall_delivery_charge / 100)
        elif self.overall_delivery_type == 'fixed':
            delivery_amount = self.overall_delivery_charge

        # Calculate NET TOTAL (without delivery charge)
        net_total = gross - discount_amount + vat_amount + service_amount
        
        # Calculate GRAND TOTAL (net total + delivery charge)
        grand_total = net_total + delivery_amount

        self.gross_total = round(gross, 2)
        self.net_total = round(net_total, 2)           # 365.0
        self.grand_total = round(grand_total, 2)       # 385.0 (NEW FIELD)
        self.payable_amount = round(grand_total, 2)    # Same as grand_total
        self.due_amount = max(0, self.payable_amount - self.paid_amount)

        super().save(update_fields=[
            "gross_total", "net_total", "grand_total", 
            "payable_amount", "due_amount"
        ])

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Walk-in Customer"
        return f"{self.invoice_no} - {customer_name}"

    @property
    def is_walk_in_customer(self):
        return self.customer_type == 'walk_in'


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