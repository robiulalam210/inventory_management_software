# returns/models.py
from django.db import models
from core.models import Company
from products.models import Product
from accounts.models import Account

class SalesReturn(models.Model):
    RETURN_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    receipt_no = models.CharField(max_length=100, blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    return_date = models.DateField()  # Remove auto_now_add=True to make it editable
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='sale_returns')
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    return_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge_type = models.CharField(max_length=50, blank=True, null=True, choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')])
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=RETURN_STATUS, default='pending')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Add this for creation timestamp

    def __str__(self):
        return f"SalesReturn #{self.id} - {self.receipt_no or 'No Receipt'}"

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            # Generate receipt number
            last_return = SalesReturn.objects.filter(company=self.company).last()
            if last_return and last_return.receipt_no:
                try:
                    last_number = int(last_return.receipt_no.split('-')[-1])
                    self.receipt_no = f"SR-{last_number + 1:04d}"
                except:
                    self.receipt_no = f"SR-0001"
            else:
                self.receipt_no = f"SR-0001"
        
        # Set default return_date if not provided
        if not self.return_date:
            from django.utils import timezone
            self.return_date = timezone.now().date()
            
        super().save(*args, **kwargs)


class SalesReturnItem(models.Model):
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    damage_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True, choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')])
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        # Calculate total based on quantity, price, and discount
        base_amount = self.unit_price * self.quantity
        
        if self.discount_type == 'percentage' and self.discount > 0:
            discount_amount = (base_amount * self.discount) / 100
        else:
            discount_amount = self.discount
            
        self.total = base_amount - discount_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} (x{self.quantity})"


class PurchaseReturn(models.Model):
    RETURN_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    supplier = models.CharField(max_length=255, blank=True, null=True)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    return_date = models.DateField()  # Remove auto_now_add=True
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase_returns')
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    return_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_charge_type = models.CharField(max_length=50, blank=True, null=True, choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')])
    return_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=RETURN_STATUS, default='pending')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PurchaseReturn #{self.id} - {self.invoice_no or 'No Invoice'}"

    def save(self, *args, **kwargs):
        # Set default return_date if not provided
        if not self.return_date:
            from django.utils import timezone
            self.return_date = timezone.now().date()
        super().save(*args, **kwargs)


class PurchaseReturnItem(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=50, blank=True, null=True, choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')])
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        # Calculate total based on quantity, price, and discount
        base_amount = self.unit_price * self.quantity
        
        if self.discount_type == 'percentage' and self.discount > 0:
            discount_amount = (base_amount * self.discount) / 100
        else:
            discount_amount = self.discount
            
        self.total = base_amount - discount_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class BadStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bad_stocks')
    quantity = models.PositiveIntegerField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    date = models.DateField(auto_now_add=True)
    reference_type = models.CharField(max_length=50, choices=[('sales_return', 'Sales Return'), ('purchase_return', 'Purchase Return'), ('direct', 'Direct')])
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Bad Stock {self.quantity} of {self.product.name}"