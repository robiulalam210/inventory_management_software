from django.contrib import admin
from .models import Category, Unit, Brand, Product, Source, Group

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'company', 'category', 'brand', 'unit', 'stock_qty', 'selling_price', 'is_active')
    list_filter = ('company', 'category', 'brand', 'unit', 'is_active')
    search_fields = ('name', 'sku', 'category__name', 'brand__name')
    readonly_fields = ('sku', 'stock_qty', 'created_at', 'updated_at')
    ordering = ('name',)
    
    # Include ALL required fields
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'name', 'sku', 'description', 'image', 'is_active')
        }),
        ('Classification', {
            'fields': ('category', 'unit', 'brand', 'group', 'source')
        }),
        ('Pricing', {
            'fields': ('purchase_price', 'selling_price')
        }),
        ('Stock Information', {
            'fields': ('opening_stock', 'stock_qty', 'alert_quantity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    # This ensures the current user's company is used by default
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form
    
    # Filter queryset to show only products from user's company
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # If you have company-based permissions, add filtering here
        return qs

# অন্যান্য মডেলগুলোর Admin কনফিগারেশন
# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ('name', 'company', 'description')
#     list_filter = ('company',)
#     search_fields = ('name',)

# @admin.register(Unit)
# class UnitAdmin(admin.ModelAdmin):
#     list_display = ('name', 'code', 'company')
#     list_filter = ('company',)
#     search_fields = ('name', 'code')

# @admin.register(Brand)
# class BrandAdmin(admin.ModelAdmin):
#     list_display = ('name', 'company')
#     list_filter = ('company',)
#     search_fields = ('name',)

# @admin.register(Group)
# class GroupAdmin(admin.ModelAdmin):
#     list_display = ('name', 'company')
#     list_filter = ('company',)
#     search_fields = ('name',)

# @admin.register(Source)
# class SourceAdmin(admin.ModelAdmin):
#     list_display = ('name', 'company')
#     list_filter = ('company',)
#     search_fields = ('name',)

# অন্যান্য মডেল সাধারণভাবে register
admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Brand)
admin.site.register(Source)
admin.site.register(Group)
