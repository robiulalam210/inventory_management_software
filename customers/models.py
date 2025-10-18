from django.db import models
from core.models import Company

# -----------------------------
# Customer
# -----------------------------
class Customer(models.Model):
    name = models.CharField(max_length=100,)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")

    def __str__(self):
        return self.name


