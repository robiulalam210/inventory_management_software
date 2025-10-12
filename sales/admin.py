from django.contrib import admin
from .models import Sale, SaleItem, Customer

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'get_customer_name', 'sale_type', 'sale_date', 'gross_total', 'net_total')
    list_filter = ['sale_type', 'sale_date']
    search_fields = ['customer__name']

    def get_customer_name(self, obj):
        return obj.customer.name
    get_customer_name.short_description = 'Customer'

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'discount', 'discount_type']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'address']
    search_fields = ['name', 'phone']
