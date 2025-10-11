from django.contrib import admin
from .models import Category, Unit, Brand, Product, Source, Group

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'brand', 'unit', 'stock_qty', 'selling_price', 'is_active')
    list_filter = ('category', 'brand', 'unit', 'is_active')
    search_fields = ('name', 'sku', 'category__name', 'brand__name')
    readonly_fields = ('sku', 'stock_qty', 'created_at', 'updated_at')
    ordering = ('name',)
    fields = ('name',  'category', 'brand', 'unit', 'purchase_price', 'selling_price', 
              'opening_stock', 'stock_qty', 'alert_quantity', 'description', 'image', 'is_active', 
              'unit_name', 'unit_sub_name', 'created_at', 'updated_at')


# অন্যান্য মডেল সাধারণভাবে register
admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Brand)
admin.site.register(Source)
admin.site.register(Group)
