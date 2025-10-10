# sales/admin.py
from django.contrib import admin
from .models import Sale, SaleItem, Customer

class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'gross_total', 'net_total', 'sale_date', 'sale_by', 'payment_method']
    list_filter = ['sale_date', 'sale_type', 'payment_method']
    date_hierarchy = 'sale_date'

class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale', 'product', 'quantity', 'unit_price', 'discount', 'discount_type']
    list_filter = ['sale__sale_date', 'product']
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'address']
    search_fields = ['name', 'phone']

admin.site.register(Sale, SaleAdmin)
admin.site.register(SaleItem, SaleItemAdmin)
admin.site.register(Customer, CustomerAdmin)

