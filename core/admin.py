from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import path
from django.db.models import Sum
from django.utils.html import format_html
from django.http import HttpResponse

from .models import User, Category, Unit, Product, Supplier, Purchase, Sale, Customer

# ----------------- User Admin -----------------
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password', 'role')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

admin.site.register(User, UserAdmin)

# ----------------- Other Models -----------------
admin.site.register(Category)
admin.site.register(Unit)
admin.site.register(Product)
admin.site.register(Supplier)
admin.site.register(Customer)

# ----------------- Purchase Admin -----------------
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('product', 'supplier', 'quantity', 'total', 'purchase_date')
    list_filter = ('supplier', 'purchase_date')
    change_list_template = "admin/purchase_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('report/', self.admin_site.admin_view(self.purchase_report), name='purchase-report'),
        ]
        return custom_urls + urls

    def purchase_report(self, request):
        qs = self.get_queryset(request)
        total_quantity = qs.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        total_amount = qs.aggregate(total_amt=Sum('total'))['total_amt'] or 0

        html = f"""
        <h1>📦 Purchase Report</h1>
        <p><strong>Total Quantity:</strong> {total_quantity}</p>
        <p><strong>Total Amount:</strong> {total_amount}</p>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Product</th>
                <th>Supplier</th>
                <th>Quantity</th>
                <th>Total</th>
                <th>Date</th>
            </tr>
        """
        for p in qs:
            html += f"""
            <tr>
                <td>{p.product}</td>
                <td>{p.supplier}</td>
                <td>{p.quantity}</td>
                <td>{p.total}</td>
                <td>{p.purchase_date}</td>
            </tr>
            """
        html += "</table>"
        return HttpResponse(html)

# ----------------- Sale Admin -----------------
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'quantity', 'total', 'sale_date')
    list_filter = ('customer', 'sale_date')
    change_list_template = "admin/sale_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('report/', self.admin_site.admin_view(self.sales_report), name='sales-report'),
        ]
        return custom_urls + urls

    def sales_report(self, request):
        qs = self.get_queryset(request)
        total_quantity = qs.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        total_amount = qs.aggregate(total_amt=Sum('total'))['total_amt'] or 0

        html = f"""
        <h1>💰 Sales Report</h1>
        <p><strong>Total Quantity Sold:</strong> {total_quantity}</p>
        <p><strong>Total Sales Amount:</strong> {total_amount}</p>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Product</th>
                <th>Customer</th>
                <th>Quantity</th>
                <th>Total</th>
                <th>Date</th>
            </tr>
        """
        for s in qs:
            html += f"""
            <tr>
                <td>{s.product}</td>
                <td>{s.customer}</td>
                <td>{s.quantity}</td>
                <td>{s.total}</td>
                <td>{s.sale_date}</td>
            </tr>
            """
        html += "</table>"
        return HttpResponse(html)


# Note: Profit/Loss and Low Stock reports are better handled in views rather than admin due to their complexity.