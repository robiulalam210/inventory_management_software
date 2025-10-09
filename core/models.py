from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from decimal import Decimal

# -------------------- User Model --------------------
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    # Solve group & permissions reverse accessor clash
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

# -------------------- Category --------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# -------------------- Unit --------------------
class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=10, blank=True, null=True)  # e.g., kg, pcs

    def __str__(self):
        return self.name

# -------------------- Product --------------------
class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, related_name='products')
    stock = models.IntegerField(default=0)  # <-- Add this

    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # current stock
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)    # per unit price
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# -------------------- Supplier --------------------
class Supplier(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# -------------------- Purchase --------------------
class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, blank=True)
    purchase_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate total
        self.total = self.price * self.quantity

        # Auto-increase stock only on new purchase
        if not self.pk:  # New purchase
            self.product.quantity += self.quantity
            self.product.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'
# -------------------- Customer --------------------
class Customer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name        
    

# -------------------- Customer --------------------
class Customer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# -------------------- Sale --------------------
class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, blank=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    # location = models.CharField(max_length=100, blank=True, null=True)  # ✅ Add location


    def save(self, *args, **kwargs):
        # Calculate total
        self.total = self.price * self.quantity

        # Auto decrease stock only for new sales
        if not self.pk:
            if self.quantity > self.product.quantity:
                raise ValueError("Not enough stock for this sale")
            self.product.quantity -= self.quantity
            self.product.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'
