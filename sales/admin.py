from django.contrib import admin
from .models import Customer, Sale, SaleItem

# --- Inline for Sale Items ---
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1  # One empty row by default
    readonly_fields = ('subtotal',)

    def subtotal(self, obj):
        return obj.qty * obj.price if obj.pk else 0
    subtotal.short_description = 'Subtotal'


# --- Sale Admin ---
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'total', 'date')
    list_filter = ('date', 'customer')
    search_fields = ('customer__name',)
    date_hierarchy = 'date'
    inlines = [SaleItemInline]


# --- Customer Admin ---
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'address')
    search_fields = ('name', 'phone')


# --- SaleItem Admin (optional standalone view) ---
@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sale', 'product', 'qty', 'price', 'subtotal_display')
    list_filter = ('sale__date',)
    search_fields = ('product__name', 'sale__customer__name')

    def subtotal_display(self, obj):
        return obj.qty * obj.price
    subtotal_display.short_description = 'Subtotal'
