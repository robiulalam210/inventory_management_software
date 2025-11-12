# products/models.py
from django.db import models, transaction, IntegrityError
from django.conf import settings
from core.models import Company
from decimal import Decimal
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
        verbose_name_plural = "Categories"
    
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
    """
    Model to generate sequential product numbers per company
    """
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE, related_name="product_sequence")
    last_number = models.PositiveIntegerField(default=10000)  # Changed from 0 to 1000
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Product Sequence"
        verbose_name_plural = "Company Product Sequences"

    @classmethod
    def get_next_sequence(cls, company):
        """
        Get next sequential number for a company with zero-padding
        """
        with transaction.atomic():
            sequence, created = cls.objects.select_for_update().get_or_create(
                company=company,
                defaults={'last_number': 10000}  # Start from 1000
            )
            sequence.last_number += 1
            sequence.save()
            return sequence.last_number  # This will return 1001, 1002, 1003, etc.

    def __str__(self):
        return f"{self.company.name} - {self.last_number:05d}"
    

class Product(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('fixed', 'Fixed'),
        ('percentage', 'Percentage'),
    ]
    
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name="products")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120, blank=True, null=True, unique=True)

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True)
    brand = models.ForeignKey('Brand', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey('Source', on_delete=models.SET_NULL, null=True, blank=True)

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
   
    opening_stock = models.PositiveIntegerField(default=0)
    stock_qty = models.PositiveIntegerField(default=0)
    alert_quantity = models.PositiveIntegerField(default=5)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='inventory-products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    discount_type = models.CharField(
        max_length=10, 
        choices=DISCOUNT_TYPE_CHOICES,
        null=True, 
        blank=True
    )
    discount_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        default=Decimal('0.00')
    )
    discount_applied_on = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['sku']),
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['brand']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_company_product_name'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})" if self.sku else self.name

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"

    @property
    def stock_status(self):
        """Returns stock status: 'out_of_stock', 'low_stock', 'in_stock'"""
        if self.stock_qty == 0:
            return "out_of_stock"
        elif self.stock_qty <= self.alert_quantity:
            return "low_stock"
        else:
            return "in_stock"

    @property
    def stock_status_code(self):
        """Returns stock status code: 0=out of stock, 1=low stock, 2=in stock"""
        if self.stock_qty == 0:
            return 0
        elif self.stock_qty <= self.alert_quantity:
            return 1
        else:
            return 2

    @property
    def final_price(self):
        """Calculate final price after discount"""
        if not self.discount_applied_on or not self.discount_value:
            return self.selling_price
        
        if self.discount_type == 'fixed':
            final_price = max(Decimal('0.00'), self.selling_price - self.discount_value)
        elif self.discount_type == 'percentage':
            discount_amount = (self.selling_price * self.discount_value) / Decimal('100.00')
            final_price = max(Decimal('0.00'), self.selling_price - discount_amount)
        else:
            final_price = self.selling_price
            
        return final_price.quantize(Decimal('0.01'))

    def _generate_company_sku(self):
        """Generate company-specific sequential SKU in format: PDT-{company_id}-{sequential_number}"""
        if not self.company:
            raise ValueError("Company is required to generate SKU")
        
        try:
            # Get next sequence number for this company
            next_num = CompanyProductSequence.get_next_sequence(self.company)
            # Format: PDT-2-01001, PDT-2-01002, etc.
            # Remove the leading zero from the format since we're starting from 1001
            return f"PDT-{self.company.id}-{next_num}"  # This will give PDT-2-1001, PDT-2-1002, etc.
        except Exception as e:
            # Fallback if sequence fails
            return self._generate_fallback_sku()

    def _generate_fallback_sku(self):
        """Generate fallback SKU using timestamp"""
        timestamp = int(time.time())
        random_suffix = random.randint(100, 999)
        company_id = self.company.id if self.company else "XX"
        return f"PDT-{company_id}-FB{timestamp}{random_suffix}"

    def clean(self):
        """Model validation"""
        from django.core.exceptions import ValidationError
        
        if self.purchase_price < 0:
            raise ValidationError("Purchase price cannot be negative")
        
        if self.selling_price < 0:
            raise ValidationError("Selling price cannot be negative")
        
        if self.discount_value and self.discount_value < 0:
            raise ValidationError("Discount value cannot be negative")
        
        # Validate discount type and value consistency
        if self.discount_value and not self.discount_type:
            raise ValidationError("Discount type is required when discount value is set")
        
        if self.discount_type and not self.discount_value:
            raise ValidationError("Discount value is required when discount type is set")

    def save(self, *args, **kwargs):
        """Custom save with SKU generation and validation"""
        is_new = self.pk is None
        
        # Validate data
        self.clean()
        
        if is_new:
            # Set initial stock
            if self.stock_qty == 0 and self.opening_stock > 0:
                self.stock_qty = self.opening_stock

            # Generate company-scoped SKU if not provided
            if not self.sku and self.company:
                try:
                    self.sku = self._generate_company_sku()
                except Exception as e:
                    self.sku = self._generate_fallback_sku()

        # Save with retry logic for IntegrityError (SKU conflicts)
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
        try:
            from purchases.models import PurchaseItem
            from sales.models import SaleItem
            
            has_purchases = PurchaseItem.objects.filter(product=self).exists()
            has_sales = SaleItem.objects.filter(product=self).exists()
            
            return not (has_purchases or has_sales)
        except (ImportError, Exception):
            # If models aren't available (during migrations) or any error, assume safe to delete
            return True

    def update_stock(self, quantity, transaction_type, update_product=True):
        """
        Update product stock quantity
        transaction_type: 'in' for increase, 'out' for decrease
        """
        if transaction_type == 'in':
            self.stock_qty += quantity
        elif transaction_type == 'out':
            if self.stock_qty < quantity:
                raise ValueError(f"Insufficient stock. Available: {self.stock_qty}, Requested: {quantity}")
            self.stock_qty -= quantity
        else:
            raise ValueError("Transaction type must be 'in' or 'out'")
        
        if update_product:
            self.save(update_fields=['stock_qty', 'updated_at'])
        
        return self.stock_qty

    def get_stock_value(self, price_type='purchase'):
        """Get total stock value based on price type"""
        if price_type == 'purchase':
            price = self.purchase_price
        elif price_type == 'selling':
            price = self.selling_price
        elif price_type == 'final':
            price = self.final_price
        else:
            price = self.purchase_price
            
        return self.stock_qty * price

    @classmethod
    def get_low_stock_products(cls, company):
        """Get products with low stock for a company"""
        return cls.objects.filter(
            company=company,
            is_active=True,
            stock_qty__lte=models.F('alert_quantity')
        ).order_by('stock_qty')

    @classmethod
    def get_out_of_stock_products(cls, company):
        """Get out-of-stock products for a company"""
        return cls.objects.filter(
            company=company,
            is_active=True,
            stock_qty=0
        )

    def get_product_summary(self):
        """Get product summary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'sku': self.sku,
            'category': self.category.name if self.category else None,
            'brand': self.brand.name if self.brand else None,
            'purchase_price': float(self.purchase_price),
            'selling_price': float(self.selling_price),
            'final_price': float(self.final_price),
            'stock_qty': self.stock_qty,
            'alert_quantity': self.alert_quantity,
            'stock_status': self.stock_status,
            'stock_status_code': self.stock_status_code,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
        }