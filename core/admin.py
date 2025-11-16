from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import User, Company, StaffRole, Staff
# core/admin.py - Fix the CompanyAdmin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import User, Company, StaffRole, Staff


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
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
        "action_buttons"
    )
    list_filter = ("is_active", "plan_type", "start_date")
    search_fields = ("name", "company_code", "phone", "email")
    readonly_fields = ("company_code", "created_at", "updated_at", "user_count", "product_count", "start_date")  # Add start_date to readonly
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
                "start_date",  # This is now readonly
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
    
    def days_until_expiry_display(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return "N/A"
        if days < 0:
            return format_html('<span style="color: red;">Expired ({} days)</span>', abs(days))
        elif days < 30:
            return format_html('<span style="color: orange;">{} days</span>', days)
        else:
            return format_html('<span style="color: green;">{} days</span>', days)
    days_until_expiry_display.short_description = "Days Until Expiry"
    
    def user_count(self, obj):
        return obj.active_user_count
    user_count.short_description = "Active Users"
    
    def action_buttons(self, obj):
        view_url = reverse("admin:core_company_change", args=[obj.id])
        users_url = reverse("admin:core_user_changelist") + f"?company__id__exact={obj.id}"
        return format_html(
            '<a href="{}" class="button">Edit</a> &nbsp; '
            '<a href="{}" class="button">View Users</a>',
            view_url, users_url
        )
    action_buttons.short_description = "Actions"
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('users', 'products')


# ... rest of your admin.py remains the same ...


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Company & Role", {
            "fields": (
                "role", 
                "company",
                "phone",
                "profile_picture"
            )
        }),
        ("Permissions", {
            "fields": (
                "can_manage_products",
                "can_manage_sales", 
                "can_manage_purchases",
                "can_manage_customers",
                "can_manage_suppliers", 
                "can_view_reports",
                "can_manage_users",
                "is_verified"
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
        "is_active", 
        "is_verified",
        "last_login",
        "permissions_summary"
    )
    
    list_filter = (
        "role", 
        "company", 
        "is_staff", 
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
        return obj.full_name
    full_name.short_description = "Full Name"
    
    def permissions_summary(self, obj):
        perms = []
        if obj.can_manage_products:
            perms.append("Products")
        if obj.can_manage_sales:
            perms.append("Sales")
        if obj.can_manage_purchases:
            perms.append("Purchases")
        if obj.can_view_reports:
            perms.append("Reports")
        return ", ".join(perms) if perms else "View Only"
    permissions_summary.short_description = "Permissions"


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = (
        "name", 
        "role_type", 
        "external_id", 
        "is_active",
        "staff_count",
        "created_at"
    )
    
    list_filter = ("role_type", "is_active")
    
    search_fields = ("name", "external_id", "description")
    
    readonly_fields = ("created_at", "staff_count")
    
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
            "fields": ("staff_count",),
            "classes": ("collapse",)
        })
    )
    
    def staff_count(self, obj):
        return obj.staff_members.count()
    staff_count.short_description = "Staff Members"


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
            '<span style="color: {};">{}</span>',
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
        return super().get_queryset(request).select_related(
            'user', 'company', 'role'
        )


admin.site.site_header = "Meherin Mart ERP Administration"
admin.site.site_title = "Meherin Mart ERP"
admin.site.index_title = "Welcome to Meherin Mart ERP Admin Panel"