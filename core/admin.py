from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group
from .models import User, Company, StaffRole, Staff, RolePermission


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
    list_per_page = 25
    
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
    days_until_expiry_display.admin_order_field = "expiry_date"
    
    def user_count(self, obj):
        count = obj.active_user_count
        url = reverse("admin:core_user_changelist") + f"?company__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    user_count.short_description = "Active Users"
    
    def product_count(self, obj):
        try:
            count = obj.products.count()
            return count
        except:
            return 0
    product_count.short_description = "Products"
    
    def action_buttons(self, obj):
        view_url = reverse("admin:core_company_change", args=[obj.id])
        users_url = reverse("admin:core_user_changelist") + f"?company__id__exact={obj.id}"
        staff_url = reverse("admin:core_staff_changelist") + f"?company__id__exact={obj.id}"
        roles_url = reverse("admin:core_staffrole_changelist") + f"?company__id__exact={obj.id}"
        
        return format_html(
            '<a href="{}" class="button" style="padding: 3px 8px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 12px;">Edit</a>'
            '<a href="{}" class="button" style="padding: 3px 8px; background: #5a9c23; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 12px;">Users</a>'
            '<a href="{}" class="button" style="padding: 3px 8px; background: #8a6d3b; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 12px;">Staff</a>'
            '<a href="{}" class="button" style="padding: 3px 8px; background: #a94442; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 12px;">Roles</a>',
            view_url, users_url, staff_url, roles_url
        )
    action_buttons.short_description = "Actions"
    action_buttons.allow_tags = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.prefetch_related('users')
        return qs.filter(users=request.user)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = (
        "staff_role",
        "module",
        "permission_badges",
        "can_export"
    )
    
    list_filter = (
        "module",
        "staff_role__role_type",
        "staff_role__company"
    )
    
    search_fields = (
        "staff_role__name",
        "module"
    )
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("staff_role", "module")
        }),
        ("Permissions", {
            "fields": ("can_view", "can_create", "can_edit", "can_delete", "can_export")
        }),
    )
    
    def permission_badges(self, obj):
        badges = []
        if obj.can_view:
            badges.append('<span style="background: #5bc0de; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px;">View</span>')
        if obj.can_create:
            badges.append('<span style="background: #5cb85c; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px;">Create</span>')
        if obj.can_edit:
            badges.append('<span style="background: #f0ad4e; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px;">Edit</span>')
        if obj.can_delete:
            badges.append('<span style="background: #d9534f; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px;">Delete</span>')
        
        return format_html(" ".join(badges))
    permission_badges.short_description = "Permissions"
    permission_badges.allow_tags = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('staff_role', 'staff_role__company')
        if request.user.is_superuser:
            return qs
        if request.user.company:
            return qs.filter(staff_role__company=request.user.company)
        return qs.none()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        ("Personal Information", {
            "fields": ("username", "password", "first_name", "last_name", "email")
        }),
        ("Company & Role", {
            "fields": (
                "role", 
                "company",
                "phone",
                "profile_picture",
                "date_of_birth"
            )
        }),
        ("Dashboard Permissions", {
            "fields": ("can_access_dashboard",),
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
        }),
        ("Status", {
            "fields": ("is_active", "is_staff", "is_superuser")
        }),
        ("Important Dates", {
            "fields": ("last_login", "date_joined", "created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )
    
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "email"),
        }),
        ("Personal Information", {
            "fields": ("first_name", "last_name", "phone", "date_of_birth")
        }),
        ("Company & Role", {
            "fields": ("role", "company")
        }),
        ("Status", {
            "fields": ("is_active", "is_staff", "is_superuser")
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
    list_per_page = 25
    
    def full_name(self, obj):
        name = obj.get_full_name()
        if name:
            return name
        return format_html('<span style="color: #999;">No Name</span>')
    full_name.short_description = "Full Name"
    full_name.admin_order_field = "first_name"
    
    def permissions_summary(self, obj):
        if obj.is_superuser:
            return format_html('<span style="color: green; font-weight: bold; background: #e8f5e8; padding: 2px 8px; border-radius: 3px;">SUPERUSER</span>')
        
        # Count modules with any permission
        modules_with_perms = []
        
        # Simplified check - just check main modules
        if obj.can_access_dashboard:
            modules_with_perms.append("Dashboard")
        
        # Check a few key modules
        if obj.sales_view or obj.sales_create or obj.sales_edit or obj.sales_delete:
            modules_with_perms.append("Sales")
        
        if obj.products_view or obj.products_create or obj.products_edit or obj.products_delete:
            modules_with_perms.append("Products")
        
        if obj.customers_view or obj.customers_create or obj.customers_edit or obj.customers_delete:
            modules_with_perms.append("Customers")
        
        if obj.reports_view or obj.reports_export:
            modules_with_perms.append("Reports")
        
        if not modules_with_perms:
            return format_html('<span style="color: orange; background: #fff3cd; padding: 2px 8px; border-radius: 3px;">No Permissions</span>')
        
        if len(modules_with_perms) <= 3:
            return ", ".join(modules_with_perms)
        else:
            return format_html('<span style="color: blue; background: #e3f2fd; padding: 2px 8px; border-radius: 3px;">{} modules</span>', len(modules_with_perms))
    
    permissions_summary.short_description = "Permissions"
    permissions_summary.allow_tags = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('company')
        if request.user.company:
            return qs.filter(company=request.user.company).select_related('company')
        return qs.none()


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = (
        "name", 
        "role_type", 
        "company",
        "permission_count",
        "staff_count",
        "is_active",
        "created_at"
    )
    
    list_filter = ("role_type", "is_active", "created_at", "company")
    
    search_fields = ("name", "description", "company__name")
    
    readonly_fields = ("created_at", "updated_at", "permission_count", "staff_count")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "role_type", "company", "is_active")
        }),
        ("Description", {
            "fields": ("description",)
        }),
        ("Default Permissions", {
            "fields": ("default_permissions",),
            "classes": ("collapse",)
        }),
        ("Statistics", {
            "fields": ("permission_count", "staff_count"),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )
    
    def permission_count(self, obj):
        count = obj.permissions.count()
        url = reverse("admin:core_rolepermission_changelist") + f"?staff_role__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    permission_count.short_description = "Permissions"
    
    def staff_count(self, obj):
        count = obj.staff_members.count()
        url = reverse("admin:core_staff_changelist") + f"?role__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)
    staff_count.short_description = "Staff Members"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('company')
        if request.user.company:
            return qs.filter(company=request.user.company).select_related('company')
        return qs.none()


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
        "employment_duration_display",
        "action_buttons"
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
    
    list_per_page = 25
    
    def user_display(self, obj):
        name = obj.user.get_full_name() or obj.user.username
        url = reverse("admin:core_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, name)
    user_display.short_description = "Staff Member"
    user_display.admin_order_field = "user__username"
    
    def status_display(self, obj):
        status_colors = {
            0: "#777",   # Inactive
            1: "#5cb85c",  # Active
            2: "#d9534f",    # Suspended
            3: "#f0ad4e", # On Leave
        }
        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: white; background: {}; padding: 3px 8px; border-radius: 10px; font-size: 12px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "Status"
    status_display.allow_tags = True
    
    def salary_display(self, obj):
        if obj.salary:
            return f"৳{obj.salary:,.2f}"
        return "-"
    salary_display.short_description = "Salary"
    salary_display.admin_order_field = "salary"
    
    def employment_duration_display(self, obj):
        days = obj.employment_duration
        if days <= 0:
            return "N/A"
        if days >= 365:
            years = days // 365
            return f"{years}y"
        elif days >= 30:
            months = days // 30
            return f"{months}m"
        else:
            return f"{days}d"
    employment_duration_display.short_description = "Duration"
    
    def action_buttons(self, obj):
        edit_url = reverse("admin:core_staff_change", args=[obj.id])
        user_url = reverse("admin:core_user_change", args=[obj.user.id])
        
        return format_html(
            '<a href="{}" class="button" style="padding: 2px 6px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;">Edit Staff</a>'
            '<a href="{}" class="button" style="padding: 2px 6px; background: #5a9c23; color: white; text-decoration: none; border-radius: 3px; margin: 1px; font-size: 11px;">Edit User</a>',
            edit_url, user_url
        )
    action_buttons.short_description = "Actions"
    action_buttons.allow_tags = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user', 'company', 'role')
        if request.user.is_superuser:
            return qs
        if request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


# Customize admin site
admin.site.site_header = "Meherin Mart ERP Administration"
admin.site.site_title = "Meherin Mart ERP"
admin.site.index_title = "Welcome to Meherin Mart ERP Admin Panel"

# Optionally unregister Group if not needed
# admin.site.unregister(Group)

# Add custom CSS for better admin interface
class CustomAdminSite(admin.AdminSite):
    def get_app_list(self, request, app_label=None):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_list = super().get_app_list(request)
        
        # Sort apps by custom order
        app_order = {
            'auth': 1,  # Authentication
            'core': 2,  # Your main app
            'sales': 3,
            'products': 4,
            'customers': 5,
            'purchases': 6,
            'accounts': 7,
            'reports': 8,
        }
        
        # Sort the app list
        app_list.sort(key=lambda x: app_order.get(x['app_label'], 999))
        
        return app_list

# Override the default admin site
admin.site.__class__ = CustomAdminSite