# products/admin.py
from django.contrib import admin
from django import forms
from .models import Category, Unit, Brand, Product, Source, Group

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'company', 'category', 'brand', 'stock_qty', 'selling_price', 'is_active')
    list_filter = ('company', 'category', 'brand', 'unit', 'is_active')
    search_fields = ('name', 'sku', 'category__name', 'brand__name')
    ordering = ('name',)
    
    # Define base fieldsets without SKU for new objects
    base_fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'name', 'description', 'image', 'is_active')
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
    
    # Fieldsets for existing objects (includes SKU)
    existing_fieldsets = (
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
    
    def get_readonly_fields(self, request, obj=None):
        """Dynamically set readonly fields"""
        readonly_fields = ['stock_qty', 'created_at', 'updated_at']
        if obj:  # Editing an existing object
            readonly_fields.append('sku')
        return readonly_fields
    
    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for new vs existing objects"""
        if obj:  # Existing object - include SKU
            return self.existing_fieldsets
        else:  # New object - no SKU field
            return self.base_fieldsets
    
    def save_model(self, request, obj, form, change):
        """Handle saving the model, ensuring company is set"""
        if not change:  # This is a new instance
            # Set created_by if not set
            if not obj.created_by:
                obj.created_by = request.user
            
            # Ensure company is set (critical for SKU generation)
            if not obj.company:
                # Try to get company from user if available
                if hasattr(request.user, 'company'):
                    obj.company = request.user.company
                else:
                    # Set the first company as default
                    from core.models import Company
                    first_company = Company.objects.first()
                    if first_company:
                        obj.company = first_company
                    else:
                        # Create a default company if none exists
                        first_company = Company.objects.create(name="Default Company")
                        obj.company = first_company
        
        super().save_model(request, obj, form, change)

# Register other models
admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Brand)
admin.site.register(Source)
admin.site.register(Group)