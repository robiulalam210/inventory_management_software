from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count
from .models import ExpenseHead, ExpenseSubHead, Expense
import logging

logger = logging.getLogger(__name__)

# ============================
# 🔹 INLINE ADMIN CLASSES
# ============================

class ExpenseSubHeadInline(admin.TabularInline):
    model = ExpenseSubHead
    extra = 1
    fields = ('name', 'is_active', 'date_created')
    readonly_fields = ('date_created',)
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)


# ============================
# 🔹 EXPENSE HEAD ADMIN
# ============================

@admin.register(ExpenseHead)
class ExpenseHeadAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company_display',
        'subhead_count',
        'total_expenses',
        'status_display',
        'date_created',
        'action_buttons'
    )
    
    list_filter = (
        'company',
        'is_active',
        'date_created'
    )
    
    search_fields = (
        'name',
        'company__name'
    )
    
    readonly_fields = (
        'date_created',
        'subhead_count',
        'total_expenses',
        'recent_expenses'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company',
                'name',
                'is_active'
            )
        }),
        ('Statistics', {
            'fields': (
                'subhead_count',
                'total_expenses',
                'recent_expenses',
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('date_created', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ExpenseSubHeadInline]
    
    def company_display(self, obj):
        return obj.company.name if obj.company else "No Company"
    company_display.short_description = 'Company'
    company_display.admin_order_field = 'company__name'
    
    def subhead_count(self, obj):
        count = obj.subheads.count()
        url = reverse('admin:expenses_expensesubhead_changelist') + f'?head__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    subhead_count.short_description = 'Sub-Heads'
    
    def total_expenses(self, obj):
        total = Expense.objects.filter(head=obj).aggregate(total=Sum('amount'))['total'] or 0
        return format_html(
            '<span style="color: #d63031; font-weight: bold;">৳{:.2f}</span>',
            total
        )
    total_expenses.short_description = 'Total Expenses'
    
    def recent_expenses(self, obj):
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        total = Expense.objects.filter(
            head=obj,
            expense_date__gte=last_30_days
        ).aggregate(total=Sum('amount'))['total'] or 0
        return f"৳{total:.2f}"
    recent_expenses.short_description = 'Last 30 Days'
    
    def status_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: #00b894; font-weight: bold;">● Active</span>'
            )
        return format_html(
            '<span style="color: #d63031; font-weight: bold;">● Inactive</span>'
        )
    status_display.short_description = 'Status'
    
    def action_buttons(self, obj):
        view_url = reverse('admin:expenses_expensehead_change', args=[obj.id])
        expenses_url = reverse('admin:expenses_expense_changelist') + f'?head__id__exact={obj.id}'
        return format_html(
            '<a href="{}" class="button" style="padding: 5px 10px; background: #0984e3; color: white; text-decoration: none; border-radius: 3px; margin-right: 5px;">Edit</a>'
            '<a href="{}" class="button" style="padding: 5px 10px; background: #00b894; color: white; text-decoration: none; border-radius: 3px;">View Expenses</a>',
            view_url, expenses_url
        )
    action_buttons.short_description = 'Actions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company', 'created_by')


# ============================
# 🔹 EXPENSE SUBHEAD ADMIN
# ============================

@admin.register(ExpenseSubHead)
class ExpenseSubHeadAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'head_display',
        'company_display',
        'expense_count',
        'total_amount',
        'status_display',
        'date_created'
    )
    
    list_filter = (
        'head',
        'head__company',
        'is_active',
        'date_created'
    )
    
    search_fields = (
        'name',
        'head__name',
        'head__company__name'
    )
    
    readonly_fields = (
        'date_created',
        'expense_count',
        'total_amount'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'head',
                'name',
                'is_active'
            )
        }),
        ('Statistics', {
            'fields': (
                'expense_count',
                'total_amount',
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('date_created', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    def head_display(self, obj):
        return obj.head.name
    head_display.short_description = 'Head'
    head_display.admin_order_field = 'head__name'
    
    def company_display(self, obj):
        return obj.head.company.name if obj.head and obj.head.company else "No Company"
    company_display.short_description = 'Company'
    
    def expense_count(self, obj):
        count = Expense.objects.filter(subhead=obj).count()
        url = reverse('admin:expenses_expense_changelist') + f'?subhead__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    expense_count.short_description = 'Expenses'
    
    def total_amount(self, obj):
        total = Expense.objects.filter(subhead=obj).aggregate(total=Sum('amount'))['total'] or 0
        return format_html(
            '<span style="color: #d63031; font-weight: bold;">৳{:.2f}</span>',
            total
        )
    total_amount.short_description = 'Total Amount'
    
    def status_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: #00b894; font-weight: bold;">● Active</span>'
            )
        return format_html(
            '<span style="color: #d63031; font-weight: bold;">● Inactive</span>'
        )
    status_display.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('head', 'head__company', 'created_by')


# ============================
# 🔹 EXPENSE ADMIN
# ============================

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'company_display',
        'head_display',
        'subhead_display',
        'amount_display',
        'payment_method_display',
        'account_display',
        'expense_date',
        'has_transaction_display',
        'status_display',
        'created_by_display',
        'action_buttons'
    )
    
    list_filter = (
        'company',
        'head',
        'subhead',
        'payment_method',
        'expense_date',
        'account'
    )
    
    search_fields = (
        'invoice_number',
        'note',
        'head__name',
        'subhead__name',
        'company__name'
    )
    
    readonly_fields = (
        'invoice_number',
        'date_created',
        'has_transaction_display',
        'transaction_link',
        'status_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'company',
                'invoice_number',
                'head',
                'subhead',
                'amount',
                'expense_date',
                'note'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_method',
                'account',
            )
        }),
        ('Transaction Information', {
            'fields': (
                'has_transaction_display',
                'transaction_link',
            ),
            'classes': ('collapse',)
        }),
        ('Status & Metadata', {
            'fields': (
                'status_display',
                'created_by',
                'date_created'
            ),
            'classes': ('collapse',)
        })
    )
    
    def company_display(self, obj):
        return obj.company.name if obj.company else "No Company"
    company_display.short_description = 'Company'
    company_display.admin_order_field = 'company__name'
    
    def head_display(self, obj):
        return obj.head.name
    head_display.short_description = 'Head'
    head_display.admin_order_field = 'head__name'
    
    def subhead_display(self, obj):
        return obj.subhead.name if obj.subhead else "—"
    subhead_display.short_description = 'Sub-Head'
    
    def amount_display(self, obj):
        return format_html(
            '<span style="color: #d63031; font-weight: bold;">৳{:.2f}</span>',
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
            obj.get_payment_method_display()
        )
    payment_method_display.short_description = 'Payment Method'
    
    def account_display(self, obj):
        if obj.account:
            return format_html(
                '<span style="color: #0984e3;">{}</span>',
                obj.account.name
            )
        return "—"
    account_display.short_description = 'Account'
    
    def has_transaction_display(self, obj):
        if obj.has_transaction():
            transaction = obj.get_associated_transaction()
            if transaction:
                url = reverse('admin:transactions_transaction_change', args=[transaction.id])
                return format_html(
                    '<span style="color: #00b894; font-weight: bold;">✓ Yes</span> '
                    '<a href="{}" style="margin-left: 10px; color: #0984e3;">View</a>',
                    url
                )
            return format_html('<span style="color: #00b894; font-weight: bold;">✓ Yes</span>')
        return format_html('<span style="color: #d63031; font-weight: bold;">✗ No</span>')
    has_transaction_display.short_description = 'Transaction'
    
    def transaction_link(self, obj):
        transaction = obj.get_associated_transaction()
        if transaction:
            url = reverse('admin:transactions_transaction_change', args=[transaction.id])
            return format_html('<a href="{}">View Transaction #{}</a>', url, transaction.id)
        return "No transaction found"
    transaction_link.short_description = 'Transaction Details'
    
    def status_display(self, obj):
        status_info = {
            'Completed': ('#00b894', '✓'),
            'Today': ('#fdcb6e', '⏳'),
            'Upcoming': ('#0984e3', '⏰')
        }
        color, icon = status_info.get(obj.status, ('#636e72', '●'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.status
        )
    status_display.short_description = 'Status'
    
    def created_by_display(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return "System"
    created_by_display.short_description = 'Created By'
    
    def action_buttons(self, obj):
        view_url = reverse('admin:expenses_expense_change', args=[obj.id])
        create_transaction_url = reverse('admin:expenses_expense_force_create_transaction', args=[obj.id])
        
        buttons = [
            f'<a href="{view_url}" class="button" style="padding: 3px 8px; background: #0984e3; color: white; text-decoration: none; border-radius: 3px; margin-right: 5px; font-size: 12px;">Edit</a>'
        ]
        
        if not obj.has_transaction() and obj.account:
            buttons.append(
                f'<a href="{create_transaction_url}" class="button" style="padding: 3px 8px; background: #00b894; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Create Transaction</a>'
            )
            
        return format_html(''.join(buttons))
    action_buttons.short_description = 'Actions'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'company', 'head', 'subhead', 'account', 'created_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    # Custom admin actions
    actions = ['create_missing_transactions', 'export_expenses']
    
    def create_missing_transactions(self, request, queryset):
        """Admin action to create missing transactions for selected expenses"""
        created_count = 0
        for expense in queryset:
            if not expense.has_transaction() and expense.account:
                transaction = expense.force_create_transaction()
                if transaction:
                    created_count += 1
        
        if created_count > 0:
            self.message_user(
                request, 
                f"Successfully created transactions for {created_count} expenses.",
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                "No transactions were created. All selected expenses already have transactions or missing account.",
                level='WARNING'
            )
    create_missing_transactions.short_description = "Create missing transactions for selected expenses"
    
    def export_expenses(self, request, queryset):
        """Admin action to export expenses (placeholder for CSV/PDF export)"""
        self.message_user(
            request,
            f"Preparing export for {queryset.count()} expenses...",
            level='INFO'
        )
    export_expenses.short_description = "Export selected expenses"


# ============================
# 🔹 CUSTOM ADMIN SITE CONFIGURATION
# ============================

# Customize admin site header
admin.site.site_header = "Expense Management System"
admin.site.site_title = "Expense Admin"
admin.site.index_title = "Expense Management Administration"

# Add custom CSS for better styling
class ExpenseAdminSite(admin.AdminSite):
    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
            )
        }


# ============================
# 🔹 CUSTOM VIEWS FOR EXPENSE ACTIONS
# ============================

from django.shortcuts import redirect
from django.contrib import messages

def force_create_transaction_view(modeladmin, request, queryset):
    """Custom admin view to force create transaction for an expense"""
    for expense in queryset:
        if expense.account and not expense.has_transaction():
            transaction = expense.force_create_transaction()
            if transaction:
                messages.success(
                    request, 
                    f"Transaction created for expense {expense.invoice_number}"
                )
            else:
                messages.error(
                    request,
                    f"Failed to create transaction for expense {expense.invoice_number}"
                )
    return redirect('admin:expenses_expense_changelist')

force_create_transaction_view.short_description = "Force create transactions"
ExpenseAdmin.force_create_transaction = force_create_transaction_view


# ============================
# 🔹 ADMIN FILTERS
# ============================

from django.contrib.admin import SimpleListFilter

class HasTransactionFilter(SimpleListFilter):
    title = 'has transaction'
    parameter_name = 'has_transaction'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has Transaction'),
            ('no', 'No Transaction'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            # This would require a more complex query in real implementation
            return queryset
        elif self.value() == 'no':
            return queryset
        return queryset


class ExpenseDateFilter(SimpleListFilter):
    title = 'expense date'
    parameter_name = 'expense_date'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('this_week', 'This Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'today':
            return queryset.filter(expense_date=timezone.now().date())
        elif self.value() == 'this_week':
            start_date = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
            return queryset.filter(expense_date__gte=start_date)
        elif self.value() == 'this_month':
            return queryset.filter(expense_date__month=timezone.now().month)
        elif self.value() == 'last_month':
            last_month = timezone.now().month - 1 if timezone.now().month > 1 else 12
            return queryset.filter(expense_date__month=last_month)
        return queryset


# Add filters to ExpenseAdmin
ExpenseAdmin.list_filter = (
    'company',
    'head',
    'subhead',
    ExpenseDateFilter,
    HasTransactionFilter,
    'payment_method',
    'account'
)

logger.info("✅ Expenses admin configuration loaded successfully!")