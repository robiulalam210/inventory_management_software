from django.db import models
from core.models import Company
from customers.models import Customer
from accounts.models import Account
from sales.models import Sale       
from django.contrib.auth import get_user_model

User = get_user_model()

class MoneyReceipt(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mr_no = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True)  # If single-invoice payment
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=100)
    payment_date = models.DateTimeField()
    remark = models.TextField(null=True, blank=True)
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    cheque_status = models.CharField(max_length=20, null=True, blank=True)
    cheque_id = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and not self.mr_no:
            # You may want to use a more robust MR number generator!
            last_id = MoneyReceipt.objects.all().order_by("-id").first()
            self.mr_no = f"MR-{1000 + (last_id.id if last_id else 0) + 1}"
        super().save(*args, **kwargs)