from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Unit, Brand, Group, Source, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active', 'product_count')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'code')

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active', 'product_count')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active', 'product_count')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active', 'product_count')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'sku', 
        'company', 
        'category', 
        'stock_status_display',
        'purchase_price', 
        'selling_price',
        'final_price',
        'stock_qty',
        'is_active'
    )
    list_filter = ('company', 'category', 'brand', 'is_active')
    search_fields = ('name', 'sku', 'description')
    readonly_fields = ('sku', 'created_at', 'updated_at', 'stock_status')
    
    def stock_status_display(self, obj):
        colors = {
            'out_of_stock': 'red',
            'low_stock': 'orange', 
            'in_stock': 'green'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.stock_status, 'black'),
            obj.stock_status.replace('_', ' ').title()
        )
    stock_status_display.short_description = 'Stock Status'