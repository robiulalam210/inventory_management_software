from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import MoneyReceipt
import logging

logger = logging.getLogger(__name__)

# ============================
# 🔹 CUSTOM ADMIN FILTERS
# ============================

class PaymentTypeFilter(admin.SimpleListFilter):
    title = 'payment type'
    parameter_name = 'payment_type'
    
    def lookups(self, request, model_admin):
        return [
            ('advance', 'Advance Payment'),
            ('specific', 'Specific Invoice'),
            ('overall', 'Overall Payment'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'advance':
            return queryset.filter(is_advance_payment=True)
        elif self.value() == 'specific':
            return queryset.filter(payment_type='specific')
        elif self.value() == 'overall':
            return queryset.filter(payment_type='overall', is_advance_payment=False)
        return queryset


class PaymentDateFilter(admin.SimpleListFilter):
    title = 'payment date'
    parameter_name = 'payment_date'
    
    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('this_week', 'This Week'),
            ('this_month', 'This Month'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'today':
            return queryset.filter(payment_date__date=timezone.now().date())
        elif self.value() == 'this_week':
            start_date = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
            return queryset.filter(payment_date__date__gte=start_date)
        elif self.value() == 'this_month':
            return queryset.filter(payment_date__year=timezone.now().year, payment_date__month=timezone.now().month)
        elif self.value() == 'last_7_days':
            start_date = timezone.now().date() - timezone.timedelta(days=7)
            return queryset.filter(payment_date__date__gte=start_date)
        elif self.value() == 'last_30_days':
            start_date = timezone.now().date() - timezone.timedelta(days=30)
            return queryset.filter(payment_date__date__gte=start_date)
        return queryset


class HasTransactionFilter(admin.SimpleListFilter):
    title = 'has transaction'
    parameter_name = 'has_transaction'
    
    def lookups(self, request, model_admin):
        return [
            ('yes', 'Has Transaction'),
            ('no', 'No Transaction'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(transaction__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(transaction__isnull=True)
        return queryset


# ============================
# 🔹 MONEY RECEIPT ADMIN
# ============================

@admin.register(MoneyReceipt)
class MoneyReceiptAdmin(admin.ModelAdmin):
    list_display = (
        'mr_no',
        'company_display',
        'customer_display',
        'payment_type_display',
        'amount_display',
        'payment_method_display',
        'payment_date',
        'sale_reference',
        'has_transaction_display',
        'payment_status_display',
        'created_by_display',
        'action_buttons'
    )
    
    list_filter = (
        'company',
        PaymentTypeFilter,
        PaymentDateFilter,
        'payment_method',
        'payment_status',
        HasTransactionFilter,
        'account',
    )
    
    search_fields = (
        'mr_no',
        'customer__name',
        'sale__invoice_no',
        'remark',
        'cheque_id'
    )
    
    readonly_fields = (
        'mr_no',
        'created_at',
        'updated_at',
        'payment_type_display',
        'has_transaction_display',
        'transaction_link',
        'payment_summary_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company',
                'mr_no',
                'customer',
                'payment_type_display',
            )
        }),
        ('Payment Details', {
            'fields': (
                'amount',
                'payment_method',
                'payment_date',
                'payment_status',
                'account',
            )
        }),
        ('Payment Type Specific', {
            'fields': (
                'is_advance_payment',
                'sale',
            ),
            'classes': ('collapse',)
        }),
        ('Transaction Information', {
            'fields': (
                'has_transaction_display',
                'transaction_link',
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'remark',
                'seller',
                'cheque_status',
                'cheque_id',
            ),
            'classes': ('collapse',)
        }),
        ('Payment Summary', {
            'fields': ('payment_summary_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def company_display(self, obj):
        return obj.company.name if obj.company else "No Company"
    company_display.short_description = 'Company'
    company_display.admin_order_field = 'company__name'
    
    def customer_display(self, obj):
        customer_name = obj.get_customer_display()
        if obj.customer:
            url = reverse('admin:customers_customer_change', args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, customer_name)
        return customer_name
    customer_display.short_description = 'Customer'
    
    def payment_type_display(self, obj):
        type_config = {
            'advance': ('#e17055', '💰', 'Advance'),
            'specific': ('#00b894', '📄', 'Specific Invoice'),
            'overall': ('#0984e3', '📊', 'Overall Payment'),
        }
        
        payment_type = 'advance' if obj.is_advance_payment else obj.payment_type
        color, icon, text = type_config.get(payment_type, ('#636e72', '●', obj.get_payment_type_display()))
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, text
        )
    payment_type_display.short_description = 'Payment Type'
    
    def amount_display(self, obj):
        return format_html(
            '<span style="color: #00b894; font-weight: bold;">৳{:.2f}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def payment_method_display(self, obj):
        method_colors = {
            'cash': '#00b894',
            'bank': '#0984e3',
            'mobile': '#6c5ce7',
            'card': '#e17055',
            'other': '#636e72'
        }
        color = method_colors.get(obj.payment_method, '#636e72')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.payment_method.title()
        )
    payment_method_display.short_description = 'Payment Method'
    
    def sale_reference(self, obj):
        if obj.sale:
            url = reverse('admin:sales_sale_change', args=[obj.sale.id])
            return format_html(
                '<a href="{}" style="color: #0984e3;">{}</a>',
                url, obj.sale.invoice_no
            )
        elif obj.is_advance_payment:
            return format_html('<span style="color: #e17055;">Advance Payment</span>')
        return "—"
    sale_reference.short_description = 'Sale Reference'
    
    def has_transaction_display(self, obj):
        if obj.transaction:
            url = reverse('admin:transactions_transaction_change', args=[obj.transaction.id])
            return format_html(
                '<span style="color: #00b894; font-weight: bold;">✓ Yes</span> '
                '<a href="{}" style="margin-left: 10px; color: #0984e3;">View</a>',
                url
            )
        return format_html('<span style="color: #d63031; font-weight: bold;">✗ No</span>')
    has_transaction_display.short_description = 'Transaction'
    
    def transaction_link(self, obj):
        if obj.transaction:
            url = reverse('admin:transactions_transaction_change', args=[obj.transaction.id])
            transaction_no = getattr(obj.transaction, 'transaction_no', f'#{obj.transaction.id}')
            return format_html('<a href="{}">View Transaction {}</a>', url, transaction_no)
        
        # Show create transaction button if no transaction exists
        create_url = reverse('admin:money_receipts_moneyreceipt_create_transaction', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding: 5px 10px; background: #00b894; color: white; text-decoration: none; border-radius: 3px;">Create Transaction</a>',
            create_url
        )
    transaction_link.short_description = 'Transaction Details'
    
    def payment_status_display(self, obj):
        status_config = {
            'completed': ('#00b894', '✓', 'Completed'),
            'pending': ('#fdcb6e', '⏳', 'Pending'),
            'failed': ('#d63031', '❌', 'Failed'),
            'cancelled': ('#636e72', '🚫', 'Cancelled'),
        }
        color, icon, text = status_config.get(obj.payment_status, ('#636e72', '●', obj.get_payment_status_display()))
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, text
        )
    payment_status_display.short_description = 'Status'
    
    def created_by_display(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "System"
    created_by_display.short_description = 'Created By'
    
    def payment_summary_display(self, obj):
        """Display payment summary in admin"""
        try:
            summary = obj.get_payment_summary()
            
            html_parts = [f'<h4>Payment Summary for {obj.mr_no}</h4>']
            
            # Basic info
            html_parts.append(f'''
                <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <strong>Amount:</strong> ৳{summary["amount"]:,.2f}<br>
                    <strong>Type:</strong> {summary["payment_type"].replace("_", " ").title()}<br>
                    <strong>Method:</strong> {summary["payment_method"]}<br>
                    <strong>Date:</strong> {summary["payment_date"][:10]}
                </div>
            ''')
            
            # Advance payment details
            if summary.get('is_advance_payment'):
                html_parts.append(f'''
                    <div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <strong>💰 Advance Payment</strong><br>
                        <strong>Customer:</strong> {summary.get('customer', 'Unknown')}<br>
                        <strong>New Balance:</strong> ৳{summary.get('new_balance', 0):,.2f}
                    </div>
                ''')
            
            # Specific invoice details
            elif summary.get('invoice_no'):
                before = summary['before_payment']
                after = summary['after_payment']
                
                html_parts.append(f'''
                    <div style="background: #d1ecf1; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <strong>📄 Specific Invoice: {summary["invoice_no"]}</strong><br>
                        <strong>Invoice Total:</strong> ৳{before["invoice_total"]:,.2f}<br>
                        <strong>Before Payment:</strong> Paid: ৳{before["previous_paid"]:,.2f}, Due: ৳{before["previous_due"]:,.2f}<br>
                        <strong>After Payment:</strong> Paid: ৳{after["current_paid"]:,.2f}, Due: ৳{after["current_due"]:,.2f}<br>
                        <strong>Applied:</strong> ৳{after["payment_applied"]:,.2f}<br>
                        <strong>Status:</strong> {summary["invoice_status"].title()}
                    </div>
                ''')
            
            # Overall payment details
            elif summary.get('customer'):
                before = summary['before_payment']
                after = summary['after_payment']
                affected = summary.get('affected_invoices', [])
                
                html_parts.append(f'''
                    <div style="background: #d4edda; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <strong>📊 Overall Payment</strong><br>
                        <strong>Customer:</strong> {summary["customer"]}<br>
                        <strong>Before Payment:</strong> Total Due: ৳{before["total_due"]:,.2f}<br>
                        <strong>After Payment:</strong> Total Due: ৳{after["total_due"]:,.2f}<br>
                        <strong>Applied:</strong> ৳{after["payment_applied"]:,.2f}<br>
                        <strong>Status:</strong> {summary["overall_status"].title()}
                    </div>
                ''')
                
                if affected:
                    html_parts.append('<strong>Affected Invoices:</strong><ul>')
                    for inv in affected:
                        html_parts.append(f'''
                            <li>{inv["invoice_no"]}: ৳{inv["amount_applied"]:,.2f} 
                            (Due: ৳{inv["previous_due"]:,.2f} → ৳{inv["current_due"]:,.2f})</li>
                        ''')
                    html_parts.append('</ul>')
            
            return format_html(''.join(html_parts))
            
        except Exception as e:
            return format_html(f'<div style="color: #d63031;">Error generating summary: {str(e)}</div>')
    
    def action_buttons(self, obj):
        view_url = reverse('admin:money_receipts_moneyreceipt_change', args=[obj.id])
        create_transaction_url = reverse('admin:money_receipts_moneyreceipt_create_transaction', args=[obj.id])
        
        buttons = [
            f'<a href="{view_url}" class="button" style="padding: 3px 8px; background: #0984e3; color: white; text-decoration: none; border-radius: 3px; margin-right: 5px; font-size: 12px;">View</a>'
        ]
        
        if not obj.transaction and obj.payment_status == 'completed' and obj.account:
            buttons.append(
                f'<a href="{create_transaction_url}" class="button" style="padding: 3px 8px; background: #00b894; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Create Transaction</a>'
            )
            
        return format_html(''.join(buttons))
    action_buttons.short_description = 'Actions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'company', 'customer', 'sale', 'account', 'transaction', 'created_by', 'seller'
        )
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    # Custom admin actions
    actions = ['create_missing_transactions', 'mark_as_completed', 'export_receipts']
    
    def create_missing_transactions(self, request, queryset):
        """Admin action to create missing transactions for selected receipts"""
        created_count = 0
        for receipt in queryset:
            if not receipt.transaction and receipt.payment_status == 'completed' and receipt.account:
                transaction = receipt.create_transaction()
                if transaction:
                    created_count += 1
        
        if created_count > 0:
            self.message_user(
                request, 
                f"Successfully created transactions for {created_count} money receipts.",
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                "No transactions were created. All selected receipts already have transactions or missing account.",
                level='WARNING'
            )
    create_missing_transactions.short_description = "Create missing transactions"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected receipts as completed"""
        updated_count = queryset.update(payment_status='completed')
        self.message_user(
            request,
            f"Successfully marked {updated_count} money receipts as completed.",
            level='SUCCESS'
        )
    mark_as_completed.short_description = "Mark as completed"
    
    def export_receipts(self, request, queryset):
        """Admin action to export receipts (placeholder for CSV/PDF export)"""
        self.message_user(
            request,
            f"Preparing export for {queryset.count()} money receipts...",
            level='INFO'
        )
    export_receipts.short_description = "Export selected receipts"


# ============================
# 🔹 CUSTOM ADMIN VIEWS
# ============================

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect

def create_transaction_view(modeladmin, request, queryset):
    """Custom admin view to create transaction for a money receipt"""
    for receipt in queryset:
        if receipt.payment_status == 'completed' and receipt.account and not receipt.transaction:
            transaction = receipt.create_transaction()
            if transaction:
                messages.success(
                    request, 
                    f"Transaction created for money receipt {receipt.mr_no}"
                )
            else:
                messages.error(
                    request,
                    f"Failed to create transaction for money receipt {receipt.mr_no}"
                )
        else:
            messages.warning(
                request,
                f"Money receipt {receipt.mr_no} cannot create transaction (check status and account)"
            )
    return redirect('admin:money_receipts_moneyreceipt_changelist')

create_transaction_view.short_description = "Create transactions for selected receipts"
MoneyReceiptAdmin.create_transaction = create_transaction_view


def create_single_transaction_view(request, receipt_id):
    """Create transaction for a single money receipt"""
    receipt = get_object_or_404(MoneyReceipt, id=receipt_id)
    
    if receipt.payment_status != 'completed':
        messages.error(request, "Cannot create transaction for non-completed payment")
    elif not receipt.account:
        messages.error(request, "Cannot create transaction without account")
    elif receipt.transaction:
        messages.warning(request, "Transaction already exists")
    else:
        transaction = receipt.create_transaction()
        if transaction:
            messages.success(request, f"Transaction created successfully: {transaction.transaction_no}")
        else:
            messages.error(request, "Failed to create transaction")
    
    return HttpResponseRedirect(reverse('admin:money_receipts_moneyreceipt_change', args=[receipt_id]))


# ============================
# 🔹 ADMIN SITE CONFIGURATION
# ============================

# Add custom URLs
from django.urls import path

def get_admin_urls():
    from django.urls import path
    return [
        path(
            'money_receipts/moneyreceipt/<path:receipt_id>/create-transaction/',
            admin.site.admin_view(create_single_transaction_view),
            name='money_receipts_moneyreceipt_create_transaction',
        ),
    ]

admin.site.get_urls = get_admin_urls

# Customize admin site
admin.site.site_header = "Money Receipts Management"
admin.site.site_title = "Money Receipts Admin"
admin.site.index_title = "Money Receipts Administration"

logger.info("✅ Money Receipts admin configuration loaded successfully!")