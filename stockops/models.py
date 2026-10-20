"""Stock Adjustment, Stocktake (গণনা), Day Close — সবই কোম্পানি অনুযায়ী আলাদা।"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class StockAdjustment(models.Model):
    REASONS = [
        ('damaged', 'Damaged'), ('expired', 'Expired'), ('lost', 'Lost / stolen'),
        ('found', 'Found / extra'), ('correction', 'Entry mistake'), ('opening', 'Opening stock'),
        ('count', 'Stock count'), ('other', 'Other'),
    ]
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='stock_adjustments')
    number = models.CharField(max_length=30, blank=True)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='stock_adjustments')
    qty_before = models.IntegerField(default=0)
    qty_after = models.IntegerField(default=0)
    change = models.IntegerField(default=0)
    value_change = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    reason = models.CharField(max_length=20, choices=REASONS, default='other')
    note = models.CharField(max_length=300, blank=True, default='')
    stocktake = models.ForeignKey('Stocktake', on_delete=models.SET_NULL, null=True, blank=True, related_name='adjustments')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['company', '-created_at'], name='stockops_ad_company_c1f0a1_idx')]

    def __str__(self):
        return f"{self.number} {self.product_id} {self.change:+d}"


class Stocktake(models.Model):
    STATUS = [('draft', 'In progress'), ('applied', 'Applied'), ('cancelled', 'Cancelled')]
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='stocktakes')
    number = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=150, blank=True, default='')
    note = models.CharField(max_length=300, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS, default='draft')
    category = models.ForeignKey('products.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.number or f"Stocktake {self.pk}"


class StocktakeLine(models.Model):
    stocktake = models.ForeignKey(Stocktake, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='+')
    system_qty = models.IntegerField(default=0)
    counted_qty = models.IntegerField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    applied_change = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['product__name', 'id']
        unique_together = [('stocktake', 'product')]


class DayClose(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='day_closes')
    date = models.DateField()
    note = models.CharField(max_length=300, blank=True, default='')
    total_expected = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_counted = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    difference = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    closed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date']
        unique_together = [('company', 'date')]


class DayCloseLine(models.Model):
    day_close = models.ForeignKey(DayClose, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=30, blank=True, default='')
    money_in = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    money_out = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    expected = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    counted = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    difference = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
