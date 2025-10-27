from django.db import models
from core.models import Company
from django.conf import settings
from django.utils import timezone
# -----------------------------
# Customer
# -----------------------------
class Customer(models.Model):
    name = models.CharField(max_length=100,)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)  # ADD THIS MISSING FIELD
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    

    def __str__(self):
        return self.name
    @property
    def status(self):
            return "Active" if self.is_active else "Inactive"

