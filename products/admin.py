# products/admin.py
from django.contrib import admin
from django import forms
from .models import Category, Unit, Brand, Product, Source, Group

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make SKU read-only only for existing instances
        if self.instance and self.instance.pk:
            self.fields['sku'].widget.attrs['readonly'] = True
            self.fields['sku'].help_text = "Auto-generated SKU (format: PDT-CompanyId-Sequence)"
        else:
            # For new instances, don't show SKU field - it will be auto-generated
            self.fields.pop('sku', None)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ('name', 'sku', 'company', 'category', 'brand', 'stock_qty', 'selling_price', 'is_active')
    list_filter = ('company', 'category', 'brand', 'unit', 'is_active')
    search_fields = ('name', 'sku', 'category__name', 'brand__name')
    readonly_fields = ('sku', 'stock_qty', 'created_at', 'updated_at')
    ordering = ('name',)
    
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