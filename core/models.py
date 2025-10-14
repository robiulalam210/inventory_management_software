from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


# ============================
# 🔹 Company Model
# ============================
class Company(models.Model):
    name = models.CharField(max_length=150, unique=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    logo = models.ImageField(upload_to='images/company/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ============================
# 🔹 Custom User Model
# ============================
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', _('Admin')
        STAFF = 'staff', _('Staff')
        CUSTOMER = 'customer', _('Customer')

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='users')

    def __str__(self):
        return f"{self.username} ({self.company})" if self.company else self.username


# ============================
# 🔹 Staff Role (Position)
# ============================
class StaffRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    def __str__(self):
        return self.name


# ============================
# 🔹 Staff Profile
# ============================
class Staff(models.Model):
    class Status(models.IntegerChoices):
        INACTIVE = 0, _('Inactive')
        ACTIVE = 1, _('Active')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='staffs')
    role = models.ForeignKey(StaffRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')

    phone = models.CharField(max_length=20, blank=True, null=True)
    image = models.ImageField(upload_to='images/staff/', blank=True, null=True)
    designation = models.CharField(max_length=120, blank=True, null=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_main_user = models.BooleanField(default=False)
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)
    joining_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_main_user']),
        ]

    def save(self, *args, **kwargs):
        # Auto assign company from user if not provided
        if not self.company and self.user and self.user.company:
            self.company = self.user.company
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.company.name}"


