# products/models.py
from django.db import models
from core.models import Company

# products/models.py
class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Group(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Source(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name



class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120, blank=True, null=True, unique=True)  # product_no
    bar_code = models.CharField(max_length=255, blank=True, null=True)

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name="products")
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True)
    brand = models.ForeignKey('Brand', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey('Source', on_delete=models.SET_NULL, null=True, blank=True)

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
   
    opening_stock = models.PositiveIntegerField(default=0)  # integer
    stock_qty = models.PositiveIntegerField(default=0)      # integer
    alert_quantity = models.PositiveIntegerField(default=5)      # integer
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='inventory-products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    unit_name = models.CharField(max_length=100, blank=True, null=True)
    unit_sub_name = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})" if self.sku else self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # চেক করা হচ্ছে নতুন প্রোডাক্ট কিনা

        # নতুন প্রোডাক্ট হলে opening_stock কে stock_qty তে সেট করা হবে
        if is_new:
            self.stock_qty = self.opening_stock

        super().save(*args, **kwargs)

        # নতুন প্রোডাক্ট হলে auto SKU generate
        if is_new and not self.sku:
            self.sku = f"PDT-{1000 + self.id}"
            super().save(update_fields=["sku"])
