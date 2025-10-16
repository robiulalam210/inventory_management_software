from django.db import models
from core.models import Company

# =========================
# মডেলগুলো (বাংলা মন্তব্য সহ)
# =========================

# ক্যাটাগরি মডেল
class Category(models.Model):
    name = models.CharField(max_length=120, )
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="categories")  # কোম্পানি ফিল্ড
    class Meta:
            constraints = [
                models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_category')
            ]
    def __str__(self):
        return self.name

# ইউনিট মডেল
class Unit(models.Model):
    name = models.CharField(max_length=60,)
    code = models.CharField(max_length=20, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="units")  # কোম্পানি ফিল্ড
    class Meta:
            constraints = [
                models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_unit')
            ]

    def __str__(self):
        return self.name

# ব্র্যান্ড মডেল
class Brand(models.Model):
    name = models.CharField(max_length=120 )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="brands")  # কোম্পানি ফিল্ড

    class Meta:
            constraints = [
                models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_brand')
            ]
    def __str__(self):
        return self.name

# গ্রুপ মডেল
class Group(models.Model):
    name = models.CharField(max_length=120 )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="groups")  # কোম্পানি ফিল্ড

    class Meta:
            constraints = [
                models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_group')
            ]

    def __str__(self):
        return self.name

# সোর্স মডেল
class Source(models.Model):
    name = models.CharField(max_length=120 )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sources")  # কোম্পানি ফিল্ড

    class Meta:
            constraints = [
                models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_source')
            ]

    def __str__(self):
        return self.name

# প্রোডাক্ট মডেল
class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")  # কোম্পানি ফিল্ড

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120, blank=True, null=True, unique=True)  # product_no

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name="products")
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True)
    brand = models.ForeignKey('Brand', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey('Source', on_delete=models.SET_NULL, null=True, blank=True)

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
   
    opening_stock = models.PositiveIntegerField(default=0)  # শুরুর স্টক
    stock_qty = models.PositiveIntegerField(default=0)      # বর্তমান স্টক
    alert_quantity = models.PositiveIntegerField(default=5)      # সতর্কতার পরিমাণ
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='inventory-products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})" if self.sku else self.name

    def save(self, *args, **kwargs):
        # Set opening stock for new products
        if not self.pk:
            self.stock_qty = self.opening_stock
        
        # Save the product first
        super().save(*args, **kwargs)
        
        # Generate SKU after save if it's not provided
        if not self.sku:
            self.sku = f"PDT-{1000 + self.id}"
            # Save only SKU field to avoid recursion
            super().save(update_fields=['sku'])