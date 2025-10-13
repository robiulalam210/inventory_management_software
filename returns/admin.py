from django.contrib import admin
from .models import SalesReturn, PurchaseReturn, BadStock

# =========================
# Sales Return Admin
# =========================
@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_sale_item', 'qty', 'return_date', 'reason')
    list_filter = ('return_date', 'sale_item')
    search_fields = ('sale_item__sale__invoice_no', 'sale_item__product__name', 'reason')

    # ForeignKey display
    def get_sale_item(self, obj):
        return f"{obj.sale_item.product.name} ({obj.sale_item.sale.invoice_no})"
    get_sale_item.short_description = 'Sale Item'


# =========================
# Purchase Return Admin
# =========================
@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_purchase', 'get_product', 'quantity', 'date')
    list_filter = ('date', 'purchase_ref', 'product_ref')
    search_fields = ('purchase_ref__invoice_no', 'product_ref__name')

    def get_purchase(self, obj):
        return obj.purchase_ref.invoice_no  # বা আপনার Purchase model অনুযায়ী
    get_purchase.short_description = 'Purchase'

    def get_product(self, obj):
        return obj.product_ref.name
    get_product.short_description = 'Product'


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