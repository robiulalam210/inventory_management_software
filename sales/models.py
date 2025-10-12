from django.db import models
from products.models import Product
from core.models import Company

# -----------------------------
# Customer
# -----------------------------
class Customer(models.Model):
    name = models.CharField(max_length=100, default="Walk-in Customer")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")

    def __str__(self):
        return self.name


# -----------------------------
# Sale
# -----------------------------
class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    invoice_no = models.CharField(max_length=20, blank=True, null=True, unique=True)
    sale_date = models.DateTimeField(auto_now_add=True)

    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_service_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)
    overall_vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Auto-generate invoice
        if is_new and not self.invoice_no:
            self.invoice_no = f"PS-{1000 + self.id}"
            super().save(update_fields=["invoice_no"])

        self.update_totals()

    def update_totals(self):
        items = self.items.all()
        gross = sum([item.subtotal() for item in items])

        discount_amount = 0
        if self.overall_discount_type == 'percent':
            discount_amount = gross * (self.overall_discount / 100)
        elif self.overall_discount_type == 'fixed':
            discount_amount = self.overall_discount

        delivery_amount = 0
        if self.overall_delivery_type == 'percent':
            delivery_amount = gross * (self.overall_delivery_charge / 100)
        elif self.overall_delivery_type == 'fixed':
            delivery_amount = self.overall_delivery_charge

        service_amount = 0
        if self.overall_service_type == 'percent':
            service_amount = gross * (self.overall_service_charge / 100)
        elif self.overall_service_type == 'fixed':
            service_amount = self.overall_service_charge

        vat_amount = 0
        if self.overall_vat_type == 'percent':
            vat_amount = gross * (self.overall_vat_amount / 100)
        elif self.overall_vat_type == 'fixed':
            vat_amount = self.overall_vat_amount

        net = gross - discount_amount + delivery_amount + service_amount + vat_amount

        self.gross_total = round(gross, 2)
        self.net_total = round(net, 2)
        self.payable_amount = round(net, 2)
        self.due_amount = max(0, self.payable_amount - self.paid_amount)

        super().save(update_fields=["gross_total","net_total","payable_amount","due_amount"])

    def __str__(self):
        return f"{self.invoice_no} - {self.customer.name}"


# -----------------------------
# SaleItem
# -----------------------------
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
        super().save(*args, **kwargs)

        # Reduce stock for new items only
        if is_new:
            if self.quantity > self.product.stock_qty:
                raise ValueError(f"Not enough stock for {self.product.name}. Available: {self.product.stock_qty}")
            self.product.stock_qty -= self.quantity
            self.product.save(update_fields=['stock_qty'])

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
