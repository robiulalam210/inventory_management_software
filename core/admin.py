from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Company, StaffRole, Staff
from accounts.models import Account  # Account from accounts app

# ==========================
# Company Admin
# ==========================
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_active', 'created_at')
    search_fields = ('name', 'phone')
    list_filter = ('is_active',)


# ==========================
# Custom User Admin
# ==========================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Add custom fields
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Company & Role', {'fields': ('role', 'company')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Company & Role', {'fields': ('role', 'company')}),
    )

    list_display = ('username', 'email', 'role', 'company', 'is_staff', 'is_active', 'last_login')
    list_filter = ('role', 'company', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'company__name')

    ordering = ('username',)
    readonly_fields = ('last_login', 'date_joined')


# ==========================
# Staff Role Admin
# ==========================
@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'external_id')
    search_fields = ('name', 'external_id')


# ==========================
# Staff Admin
# ==========================
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'role', 'status', 'is_main_user', 'phone', 'joining_date')
    list_filter = ('company', 'status', 'role', 'is_main_user')
    search_fields = ('user__username', 'user__email', 'role__name', 'phone')
    readonly_fields = ('created_at', 'updated_at')
