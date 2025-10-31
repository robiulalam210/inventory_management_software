# returns/admin.py
from django.contrib import admin
from .models import SalesReturn, SalesReturnItem, PurchaseReturn, PurchaseReturnItem, BadStock

class SalesReturnItemInline(admin.TabularInline):
    model = SalesReturnItem
    extra = 1

@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = ['receipt_no', 'customer_name', 'return_date', 'return_amount', 'status', 'company']
    list_filter = ['status', 'return_date', 'company']
    search_fields = ['receipt_no', 'customer_name']
    inlines = [SalesReturnItemInline]
    
    # Exclude return_date from the form since it's auto-set
    exclude = ['return_date']
    
    # Or use fieldsets to control which fields are displayed
    # fieldsets = [
    #     (None, {'fields': ['receipt_no', 'customer_name', 'account', 'payment_method']}),
    #     ('Return Details', {'fields': ['return_charge', 'return_charge_type', 'return_amount', 'reason', 'status']}),
    #     ('Company', {'fields': ['company']}),
    # ]

class PurchaseReturnItemInline(admin.TabularInline):
    model = PurchaseReturnItem
    extra = 1

@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ['invoice_no', 'supplier', 'return_date', 'return_amount', 'status', 'company']
    list_filter = ['status', 'return_date', 'company']
    search_fields = ['invoice_no', 'supplier']
    inlines = [PurchaseReturnItemInline]
    exclude = ['return_date']

@admin.register(BadStock)
class BadStockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'date', 'reference_type', 'company']
    list_filter = ['date', 'reference_type', 'company']
    search_fields = ['product__name', 'reason']