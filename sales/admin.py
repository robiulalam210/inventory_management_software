from django.contrib import admin
from .models import Sale, SaleItem, Customer

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'sale_type', 'sale_date', 'gross_total', 'net_total', 'overall_discount', 'payable_amount']
    list_filter = ['sale_type', 'sale_date']
    search_fields = ['customer__name']

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'discount', 'discount_type']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'address']
    search_fields = ['name', 'phone']
