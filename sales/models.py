from django.db import models
from products.models import Product

# গ্রাহক মডেল
class Customer(models.Model):
    name = models.CharField(max_length=100, default="Walk-in Customer")
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")

    def __str__(self):
        return self.name


# বিক্রয় মডেল
class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]
    PAYMENT_METHOD_CHOICES = [('cash', 'Cash'), ('bank', 'Bank'), ('cheque', 'Cheque'), ('mobile', 'Mobile')]

    customer = models.ForeignKey(Customer, on_delete=models.SET_DEFAULT, default=1, related_name='sales')
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    sale_date = models.DateTimeField(auto_now_add=True)
    sale_by = models.CharField(max_length=100, blank=True, null=True)
    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_discount_type = models.CharField(max_length=20, blank=True, null=True)
    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_delivery_charge_type = models.CharField(max_length=20, blank=True, null=True)
    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overall_vat_type = models.CharField(max_length=20, blank=True, null=True)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')

    def __str__(self):
        return f"বিক্রয় #{self.id} - {self.customer.name}"


# বিক্রয় আইটেম
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=20, blank=True, null=True)

    def subtotal(self):
        if self.discount_type == "%":
            return (self.quantity * self.unit_price) - ((self.quantity * self.unit_price) * self.discount / 100)
        return (self.quantity * self.unit_price) - self.discount

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
