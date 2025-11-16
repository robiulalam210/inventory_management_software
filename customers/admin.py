from django.contrib import admin
from django.utils.html import format_html
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'client_no',
        'name',
        'company',
        'phone',
        'email',
        'advance_balance_display',
        'total_sales_count',
        'total_purchase_amount',
        'status_display',
        'date_created'
    )
    
    list_filter = (
        'company',
        'is_active',
        'date_created'
    )
    
    search_fields = (
        'name',
        'client_no',
        'phone',
        'email',
        'company__name'
    )
    
    readonly_fields = (
        'client_no',
        'date_created',
        'advance_balance',
        'total_sales_count',
        'total_purchase_amount'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company',
                'client_no',
                'name',
                'phone',
                'email',
                'address'
            )
        }),
        ('Financial Information', {
            'fields': (
                'advance_balance',
                'total_sales_count',
                'total_purchase_amount',
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'date_created',
                'created_by'
            )
        })
    )
    
    def advance_balance_display(self, obj):
        if obj.advance_balance > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">৳{:.2f}</span>',
                obj.advance_balance
            )
        return format_html(
            '<span style="color: gray;">৳{:.2f}</span>',
            obj.advance_balance
        )
    advance_balance_display.short_description = 'Advance Balance'
    
    def status_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">● Active</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">● Inactive</span>'
        )
    status_display.short_description = 'Status'
    
    def total_sales_count(self, obj):
        from sales.models import Sale
        return Sale.objects.filter(customer=obj, company=obj.company).count()
    total_sales_count.short_description = 'Total Sales'
    
    def total_purchase_amount(self, obj):
        from sales.models import Sale
        from django.db.models import Sum
        result = Sale.objects.filter(
            customer=obj, 
            company=obj.company
        ).aggregate(total=Sum('grand_total'))
        return f"৳{result['total'] or 0:.2f}"
    total_purchase_amount.short_description = 'Total Purchases'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company', 'created_by')