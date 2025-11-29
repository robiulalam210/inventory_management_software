from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group
from .models import User, Company, StaffRole, Staff


class SuperUserAdmin(admin.ModelAdmin):
    """Base class for models that should be fully accessible to superusers"""
    
    def has_module_permission(self, request):
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Company)
class CompanyAdmin(SuperUserAdmin):
    list_display = (
        "name", 
        "company_code", 
        "phone", 
        "is_active", 
        "plan_type", 
        "start_date", 
        "expiry_date",
        "days_until_expiry_display",
        "user_count",
        "product_count",
        "action_buttons"
    )
    list_filter = ("is_active", "plan_type", "start_date", "created_at")
    search_fields = ("name", "company_code", "phone", "email", "trade_license")
    readonly_fields = ("company_code", "start_date", "created_at", "updated_at", "user_count", "product_count")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "company_code", "trade_license", "logo")
        }),
        ("Contact Information", {
            "fields": ("address", "phone", "email", "website")
        }),
        ("Business Settings", {
            "fields": ("currency", "timezone", "fiscal_year_start")
        }),
        ("Subscription & Limits", {
            "fields": (
                "plan_type", 
                "start_date",  # Keep it here but it will be readonly
                "expiry_date", 
                "is_active",
                "max_users", 
                "max_products", 
                "max_branches"
            )
        }),
        ("Statistics", {
            "fields": ("user_count", "product_count"),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )
    
    # Add this method to handle the add form separately
    def get_fieldsets(self, request, obj=None):
        if obj is None:  # This is an add form
            # Exclude start_date from add form since it's auto-generated
            add_fieldsets = (
                ("Basic Information", {
                    "fields": ("name", "trade_license", "logo")
                }),
                ("Contact Information", {
                    "fields": ("address", "phone", "email", "website")
                }),
                ("Business Settings", {
                    "fields": ("currency", "timezone", "fiscal_year_start")
                }),
                ("Subscription & Limits", {
                    "fields": (
                        "plan_type", 
                        "expiry_date", 
                        "is_active",
                        "max_users", 
                        "max_products", 
                        "max_branches"
                    )
                }),
            )
            return add_fieldsets
        return super().get_fieldsets(request, obj)
    
    def days_until_expiry_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return "N/A"
        if days < 0:
            return format_html('<span style="color: red; font-weight: bold;">Expired ({} days ago)</span>', abs(days))
        elif days < 7:
            return format_html('<span style="color: red; font-weight: bold;">{} days</span>', days)
        elif days < 30:
            return format_html('<span style="color: orange;">{} days</span>', days)
        else:
            return format_html('<span style="color: green;">{} days</span>', days)
    days_until_expiry_display.short_description = "Expiry Status"
    
    def user_count(self, obj):
        count = obj.active_user_count
        url = reverse("admin:core_user_changelist") + f"?company__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    user_count.short_description = "Active Users"
    
    def product_count(self, obj):
        count = obj.products.count()
        # You can add a link to products if you have a Product model
        return count
    product_count.short_description = "Products"
    
    def action_buttons(self, obj):
        view_url = reverse("admin:core_company_change", args=[obj.id])
        users_url = reverse("admin:core_user_changelist") + f"?company__id__exact={obj.id}"
        staff_url = reverse("admin:core_staff_changelist") + f"?company__id__exact={obj.id}"
        
        return format_html(
            '<a href="{}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Edit</a>'
            '<a href="{}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Users</a>'
            '<a href="{}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Staff</a>',
            view_url, users_url, staff_url
        )
    action_buttons.short_description = "Actions"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.prefetch_related('users', 'products')
        return qs.filter(users=request.user)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Company & Role", {
            "fields": (
                "role", 
                "company",
                "phone",
                "profile_picture",
                "date_of_birth"
            )
        }),
        ("Dashboard & Product Permissions", {
            "fields": (
                "can_access_dashboard",
                "can_manage_products",
            ),
            "classes": ("collapse",)
        }),
        ("Sales & Money Receipt Permissions", {
            "fields": (
                "sales_view", "sales_create", "sales_edit", "sales_delete",
                "money_receipt_view", "money_receipt_create", "money_receipt_edit", "money_receipt_delete",
            ),
            "classes": ("collapse",)
        }),
        ("Purchases & Products Permissions", {
            "fields": (
                "purchases_view", "purchases_create", "purchases_edit", "purchases_delete",
                "products_view", "products_create", "products_edit", "products_delete",
            ),
            "classes": ("collapse",)
        }),
        ("Accounts & Customers Permissions", {
            "fields": (
                "accounts_view", "accounts_create", "accounts_edit", "accounts_delete",
                "customers_view", "customers_create", "customers_edit", "customers_delete",
            ),
            "classes": ("collapse",)
        }),
        ("Suppliers & Expense Permissions", {
            "fields": (
                "suppliers_view", "suppliers_create", "suppliers_edit", "suppliers_delete",
                "expense_view", "expense_create", "expense_edit", "expense_delete",
            ),
            "classes": ("collapse",)
        }),
        ("Return & Reports Permissions", {
            "fields": (
                "return_view", "return_create", "return_edit", "return_delete",
                "reports_view", "reports_create", "reports_export",
            ),
            "classes": ("collapse",)
        }),
        ("Users & Administration Permissions", {
            "fields": (
                "users_view", "users_create", "users_edit", "users_delete",
                "administration_view", "administration_create", "administration_edit", "administration_delete",
            ),
            "classes": ("collapse",)
        }),
        ("Settings & Verification", {
            "fields": (
                "settings_view", "settings_edit",
                "is_verified", "last_login_ip"
            ),
            "classes": ("collapse",)
        })
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Company & Role", {
            "fields": (
                "role", 
                "company",
                "phone"
            )
        }),
    )

    list_display = (
        "username", 
        "email", 
        "full_name",
        "role", 
        "company", 
        "is_staff", 
        "is_superuser",
        "is_active", 
        "is_verified",
        "last_login",
        "permissions_summary"
    )
    
    list_filter = (
        "role", 
        "company", 
        "is_staff", 
        "is_superuser",
        "is_active", 
        "is_verified",
        "last_login"
    )
    
    search_fields = (
        "username", 
        "email", 
        "first_name", 
        "last_name",
        "company__name",
        "phone"
    )
    
    readonly_fields = (
        "last_login", 
        "date_joined",
        "created_at",
        "updated_at",
        "last_login_ip"
    )
    
    ordering = ("username",)
    
    def full_name(self, obj):
        return obj.get_full_name() or "No Name"
    full_name.short_description = "Full Name"
    
    def permissions_summary(self, obj):
        if obj.is_superuser:
            return format_html('<span style="color: green; font-weight: bold;">SUPERUSER (All Permissions)</span>')
        
        # Count active permissions based on your actual field names
        perms_count = 0
        modules = []
        
        # Check each module for any permission
        permission_methods = [
            ('Dashboard', obj.can_access_dashboard),
            ('Sales', obj.sales_view or obj.sales_create or obj.sales_edit or obj.sales_delete),
            ('Money Receipt', obj.money_receipt_view or obj.money_receipt_create or obj.money_receipt_edit or obj.money_receipt_delete),
            ('Purchases', obj.purchases_view or obj.purchases_create or obj.purchases_edit or obj.purchases_delete),
            ('Products', obj.products_view or obj.products_create or obj.products_edit or obj.products_delete),
            ('Accounts', obj.accounts_view or obj.accounts_create or obj.accounts_edit or obj.accounts_delete),
            ('Customers', obj.customers_view or obj.customers_create or obj.customers_edit or obj.customers_delete),
            ('Suppliers', obj.suppliers_view or obj.suppliers_create or obj.suppliers_edit or obj.suppliers_delete),
            ('Expense', obj.expense_view or obj.expense_create or obj.expense_edit or obj.expense_delete),
            ('Return', obj.return_view or obj.return_create or obj.return_edit or obj.return_delete),
            ('Reports', obj.reports_view or obj.reports_create or obj.reports_export),
            ('Users', obj.users_view or obj.users_create or obj.users_edit or obj.users_delete),
            ('Admin', obj.administration_view or obj.administration_create or obj.administration_edit or obj.administration_delete),
            ('Settings', obj.settings_view or obj.settings_edit),
        ]
        
        for module_name, has_perm in permission_methods:
            if has_perm:
                modules.append(module_name)
                perms_count += 1
        
        if perms_count == 0:
            return format_html('<span style="color: orange;">No Permissions</span>')
        elif perms_count <= 3:
            return ", ".join(modules)
        else:
            return format_html('<span style="color: blue;">{} modules</span>', perms_count)
    
    permissions_summary.short_description = "Permissions"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('company')
        return qs.filter(company=request.user.company)


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = (
        "name", 
        "role_type", 
        "external_id", 
        "is_active",
        "staff_count",
        "company_count",
        "created_at"
    )
    
    list_filter = ("role_type", "is_active", "created_at")
    
    search_fields = ("name", "external_id", "description")
    
    readonly_fields = ("created_at", "staff_count", "company_count")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "role_type", "external_id", "is_active")
        }),
        ("Description", {
            "fields": ("description",)
        }),
        ("Default Permissions", {
            "fields": ("default_permissions",),
            "classes": ("collapse",)
        }),
        ("Statistics", {
            "fields": ("staff_count", "company_count"),
            "classes": ("collapse",)
        })
    )
    
    def staff_count(self, obj):
        return obj.staff_members.count()
    staff_count.short_description = "Staff Members"
    
    def company_count(self, obj):
        # Count distinct companies using this role
        from django.db.models import Count
        return obj.staff_members.values('company').distinct().count()
    company_count.short_description = "Companies Using"


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        "user_display",
        "company", 
        "role", 
        "designation",
        "employment_type",
        "status_display", 
        "is_main_user", 
        "phone", 
        "joining_date",
        "salary_display",
        "employment_duration_display"
    )
    
    list_filter = (
        "company", 
        "status", 
        "role", 
        "is_main_user",
        "employment_type",
        "joining_date"
    )
    
    search_fields = (
        "user__username", 
        "user__email", 
        "user__first_name",
        "user__last_name",
        "role__name", 
        "phone",
        "employee_id",
        "designation"
    )
    
    readonly_fields = (
        "created_at", 
        "updated_at",
        "employee_id",
        "employment_duration",
        "total_compensation"
    )
    
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "user",
                "company", 
                "role",
                "employee_id",
                "image"
            )
        }),
        ("Employment Details", {
            "fields": (
                "designation",
                "department",
                "employment_type",
                "joining_date",
                "leaving_date",
                "contract_end_date"
            )
        }),
        ("Compensation", {
            "fields": (
                "salary",
                "commission", 
                "bonus",
                "total_compensation"
            )
        }),
        ("Status & Contact", {
            "fields": (
                "status",
                "is_main_user",
                "phone", 
                "alternate_phone",
                "address",
                "emergency_contact",
                "emergency_phone"
            )
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )
    
    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_display.short_description = "Staff Member"
    user_display.admin_order_field = "user__username"
    
    def status_display(self, obj):
        status_colors = {
            0: "gray",   # Inactive
            1: "green",  # Active
            2: "red",    # Suspended
            3: "orange", # On Leave
        }
        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "Status"
    
    def salary_display(self, obj):
        if obj.salary:
            return f"৳{obj.salary:,.2f}"
        return "-"
    salary_display.short_description = "Salary"
    
    def employment_duration_display(self, obj):
        days = obj.employment_duration
        if days is None:
            return "N/A"
        if days >= 365:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''}"
        elif days >= 30:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            return f"{days} day{'s' if days > 1 else ''}"
    employment_duration_display.short_description = "Duration"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user', 'company', 'role')
        if request.user.is_superuser:
            return qs
        return qs.filter(company=request.user.company)


# Customize admin site
admin.site.site_header = "Meherin Mart ERP Administration"
admin.site.site_title = "Meherin Mart ERP"
admin.site.index_title = "Welcome to Meherin Mart ERP Admin Panel"

# Unregister default Group if not needed
# admin.site.unregister(Group)