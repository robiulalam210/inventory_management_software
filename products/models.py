# products/models.py
from django.db import models
from django.conf import settings
from core.models import Company

class Category(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="categories")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_category')
        ]
    
    def __str__(self):
        return self.name

class Unit(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=20, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="units")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_unit')
        ]

    def __str__(self):
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=120)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="brands")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_brand')
        ]
    
    def __str__(self):
        return self.name

class Group(models.Model):
    name = models.CharField(max_length=120)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="groups")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_group')
        ]

    def __str__(self):
        return self.name

class Source(models.Model):
    name = models.CharField(max_length=120)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sources")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_source')
        ]

    def __str__(self):
        return self.name

class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120, blank=True, null=True, unique=True)

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name="products")
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True)
    brand = models.ForeignKey('Brand', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey('Source', on_delete=models.SET_NULL, null=True, blank=True)

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
   
    opening_stock = models.PositiveIntegerField(default=0)
    stock_qty = models.PositiveIntegerField(default=0)
    alert_quantity = models.PositiveIntegerField(default=5)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='inventory-products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})" if self.sku else self.name

    @property
    def stock_status(self):
        """Returns stock status: 0=out of stock, 1=low stock, 2=in stock"""
        if self.stock_qty == 0:
            return 0  # Out of stock
        elif self.stock_qty <= self.alert_quantity:
            return 1  # Low stock
        else:
            return 2  # In stock

    def save(self, *args, **kwargs):
        if not self.pk:
            self.stock_qty = self.opening_stock
        
        super().save(*args, **kwargs)
        
        if not self.sku:
            self.sku = f"PDT-{1000 + self.id}"
            super().save(update_fields=['sku'])