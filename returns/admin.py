from django.contrib import admin
from .models import SalesReturn, PurchaseReturn, BadStock, SalesReturnItem
from .models import PurchaseReturn, PurchaseReturnItem, BadStock

# =========================

class SalesReturnItemInline(admin.TabularInline):
    model = SalesReturnItem
    extra = 1
    fields = ('product_name', 'quantity', 'unit_price', 'discount', 'discount_type')
    readonly_fields = ('product_name',)
    show_change_link = True


@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'invoice_no', 
        'return_date', 
        'payment_method', 
        'reason', 
        'discount', 
        'vat', 
        'delivery_charge'
    )
    list_filter = ('return_date', 'payment_method', 'company')
    search_fields = ('invoice_no', 'reason', 'account__name')
    inlines = [SalesReturnItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs


@admin.register(SalesReturnItem)
class SalesReturnItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sales_return', 'product_name', 'quantity', 'unit_price', 'discount')
    search_fields = ('product_name',)
    list_filter = ('sales_return__return_date',)

# =========================
# Purchase Return Admin

class PurchaseReturnItemInline(admin.TabularInline):
    model = PurchaseReturnItem
    extra = 1
    fields = ('product_name', 'qty', 'price', 'discount', 'discount_type')
    readonly_fields = ('product_name',)
    show_change_link = True


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_purchase', 'date', 'payment_method', 'return_amount')
    list_filter = ('date', 'payment_method')
    search_fields = ('purchase_ref__invoice_no',)
    inlines = [PurchaseReturnItemInline]

    def get_purchase(self, obj):
        return obj.purchase_ref.invoice_no
    get_purchase.short_description = 'Purchase'

# =========================
# Bad Stock Admin
# =========================
@admin.register(BadStock)
class BadStockAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_product', 'qty', 'date', 'reason')
    list_filter = ('date', 'product')
    search_fields = ('product__name', 'reason')

    def get_product(self, obj):
        return obj.product.name
    get_product.short_description = 'Product'