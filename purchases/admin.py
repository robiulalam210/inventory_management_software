# branch_warehouse/admin.py
from django.contrib import admin
from .models import Purchase, PurchaseItem
from core.models import Company
from django.contrib.auth import get_user_model


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'supplier', 'purchase_date', 'grand_total', 'paid_amount', 'due_amount', 'payment_status', 'company')
    list_filter = ('payment_status', 'purchase_date', 'company')
    search_fields = ('invoice_no', 'supplier__name', 'remark')
    date_hierarchy = 'purchase_date'
    readonly_fields = ('created_by', 'updated_by', 'date_created', 'date_updated')
    raw_id_fields = ('supplier', 'account')
    
    def get_queryset(self, request):
        """Filter purchases by company for non-superusers"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company'):
            return qs.filter(company=request.user.company)
        return qs
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict company choices for non-superusers"""
        if db_field.name == "company":
            if not request.user.is_superuser and hasattr(request.user, 'company'):
                kwargs["queryset"] = Company.objects.filter(id=request.user.company.id)
        elif db_field.name in ["created_by", "updated_by"]:
            kwargs["queryset"] = get_user_model().objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Set created_by/updated_by users"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'product', 'qty', 'price', 'subtotal')
    list_filter = ('purchase__purchase_date',)
    search_fields = ('product__name', 'batch_no')
    raw_id_fields = ('purchase', 'product')
    
    def get_queryset(self, request):
        """Filter purchase items by company"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company'):
            return qs.filter(purchase__company=request.user.company)
        return qs