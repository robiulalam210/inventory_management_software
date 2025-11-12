from django.db import models
from core.models import Company
from django.conf import settings
from django.utils import timezone

class Customer(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    client_no = models.CharField(max_length=20, blank=True, null=True)  # Make nullable

    def save(self, *args, **kwargs):
        """Custom save method to handle client number generation"""
        is_new = self.pk is None
        
        # Generate client number for new customers if not provided
        if is_new and not self.client_no:
            # Count existing customers for this company to determine next number
            existing_count = Customer.objects.filter(
                company=self.company,
                client_no__isnull=False
            ).count()
            new_number = 1001 + existing_count
            self.client_no = f"CU-{new_number}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def status(self):
        return "Active" if self.is_active else "Inactive"