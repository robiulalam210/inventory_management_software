# sales/admin.py - FIXED VERSION
from django.contrib import admin
from django.utils.html import format_html
from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    readonly_fields = ('subtotal',)
    fields = ('product', 'quantity', 'unit_price', 'discount', 'discount_type', 'subtotal')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_no',
        'company',
        'customer_display',
        'sale_type',
        'grand_total',
        'paid_amount',
        'due_amount',
        'payment_status_display',
        'sale_date'
    )
    list_filter = (
        'company',
        'sale_type',
        'customer_type',
        'payment_status',
        'sale_date'
    )
    search_fields = (
        'invoice_no',
        'customer__name',
        'customer_name'
    )
    readonly_fields = (  # FIXED: Remove 'created_at' as it doesn't exist in Sale model
        'invoice_no',
        'gross_total',
        'net_total',
        'grand_total',
        'payable_amount',
        'due_amount',
        'change_amount',
    )
    inlines = [SaleItemInline]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company',
                'invoice_no',
                'sale_type',
                'customer_type',
                'customer',
                'customer_name'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_status',
                'payment_method',
                'account',
                'gross_total',
                'net_total',
                'grand_total',
                'payable_amount',
                'paid_amount',
                'due_amount',
                'change_amount'
            )
        }),
        ('Charges & Discounts', {
            'fields': (
                'overall_discount',
                'overall_discount_type',
                'overall_vat_amount',
                'overall_vat_type',
                'overall_service_charge',
                'overall_service_type',
                'overall_delivery_charge',
                'overall_delivery_type'
            )
        }),
        ('Additional Information', {
            'fields': (
                'with_money_receipt',
                'remark',
                'sale_by',
                'created_by',
                'sale_date'
            )
        })
    )

    def customer_display(self, obj):
        return obj.get_customer_display()
    customer_display.short_description = 'Customer'

    def payment_status_display(self, obj):
        colors = {
            'paid': 'green',
            'partial': 'orange',
            'pending': 'gray',
            'overdue': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.payment_status, 'black'),
            obj.get_payment_status_display()
        )
    payment_status_display.short_description = 'Payment Status'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'company', 'customer', 'sale_by', 'created_by'
        )

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        'sale',
        'product',
        'quantity',
        'unit_price',
        'discount_display',
        'subtotal'
    )
    list_filter = ('sale__company', 'sale__sale_date')
    search_fields = ('sale__invoice_no', 'product__name')
    readonly_fields = ('subtotal',)

    def discount_display(self, obj):
        if obj.discount:
            return f"{obj.discount} ({obj.get_discount_type_display()})"
        return "No Discount"
    discount_display.short_description = 'Discount'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'sale', 'product'
        )