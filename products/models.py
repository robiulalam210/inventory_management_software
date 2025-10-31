# products/models.py
from django.db import models, transaction, IntegrityError
from django.conf import settings
from core.models import Company
import time
import random

class Category(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="categories")
    is_active = models.BooleanField(default=True)

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
    is_active = models.BooleanField(default=True)

    
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
    is_active = models.BooleanField(default=True)

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
    is_active = models.BooleanField(default=True)

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
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_company_per_source')
        ]

    def __str__(self):
        return self.name


class CompanyProductSequence(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='product_sequence')
    last_number = models.PositiveIntegerField(default=10000)  # Start from 10000

    @classmethod
    def get_next_sequence(cls, company):
        """Get next sequence number with proper locking"""
        with transaction.atomic():
            # Use select_for_update to lock the row
            sequence, created = cls.objects.select_for_update().get_or_create(
                company=company,
                defaults={'last_number': 10000}
            )
            # Always increment - this ensures we get 10001, 10002, etc.
            sequence.last_number += 1
            sequence.save()
            return sequence.last_number

class CompanyProductSequence(models.Model):
    """
    Model to generate sequential product numbers per company
    """
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE, related_name="product_sequence")
    last_number = models.PositiveIntegerField(default=1000)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Product Sequence"
        verbose_name_plural = "Company Product Sequences"

    @classmethod
    def get_next_sequence(cls, company):
        """
        Get next sequential number for a company
        """
        with transaction.atomic():
            sequence, created = cls.objects.select_for_update().get_or_create(
                company=company,
                defaults={'last_number': 1000}
            )
            sequence.last_number += 1
            sequence.save()
            return sequence.last_number

    def __str__(self):
        return f"{self.company.name} - {self.last_number}"

class Product(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name="products")
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

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['sku']),
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

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

    def _generate_sku_with_company_id(self):
        """Generate SKU in format: PDT-CompanyId-10001"""
        if not self.company:
            raise ValueError("Company is required to generate SKU")
        
        try:
            # Get next sequence number for this company
            next_num = CompanyProductSequence.get_next_sequence(self.company)
            # Format: PDT-1-10001, PDT-2-10001, etc.
            sku = f"PDT-{self.company.id}-{next_num:05d}"
            return sku
        except Exception as e:
            # Fallback if sequence fails
            return self._generate_fallback_sku()

    def _generate_fallback_sku(self):
        """Generate a fallback SKU using timestamp and random number"""
        timestamp = int(time.time())
        random_suffix = random.randint(100, 999)
        company_id = self.company.id if self.company else "0"
        return f"PDT-{company_id}-{timestamp}{random_suffix}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            # Set initial stock
            if self.stock_qty == 0:
                self.stock_qty = self.opening_stock

            # Generate company-scoped SKU if not provided
            if not self.sku and self.company:
                try:
                    self.sku = self._generate_sku_with_company_id()
                except Exception as e:
                    self.sku = self._generate_fallback_sku()

        # Save with retry logic for IntegrityError
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break  # Success, exit the loop
            except IntegrityError as e:
                if 'sku' in str(e).lower() and is_new and attempt < max_retries - 1:
                    # Regenerate SKU and retry
                    self.sku = self._generate_fallback_sku()
                    continue
                else:
                    # Re-raise the exception if we've exhausted retries or it's not a SKU error
                    raise

    def can_be_deleted(self):
        """
        Check if product can be safely deleted
        (no related purchase/sale transactions)
        """
        from purchases.models import PurchaseItem
        from sales.models import SaleItem
        
        has_purchases = PurchaseItem.objects.filter(product=self).exists()
        has_sales = SaleItem.objects.filter(product=self).exists()
        
        return not (has_purchases or has_sales)

    def update_stock(self, quantity, transaction_type):
        """
        Update product stock quantity
        transaction_type: 'in' for increase, 'out' for decrease
        """
        if transaction_type == 'in':
            self.stock_qty += quantity
        elif transaction_type == 'out':
            if self.stock_qty >= quantity:
                self.stock_qty -= quantity
            else:
                raise ValueError("Insufficient stock")
        
        self.save(update_fields=['stock_qty', 'updated_at'])