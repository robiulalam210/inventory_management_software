from django.contrib import admin
from .models import Account
from core.models import Company


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ac_type', 'number', 'balance', 'company', 'is_active')
    list_filter = ('ac_type', 'is_active', 'company')
    search_fields = ('name', 'number', 'bank_name', 'branch')
    list_editable = ('is_active',)
    readonly_fields = ('ac_no', 'balance', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        """Filter accounts by company for non-superusers"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by the user's company
        if hasattr(request.user, 'company'):
            return qs.filter(company=request.user.company)
        return qs
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict company choices for non-superusers"""
        if db_field.name == "company":
            if not request.user.is_superuser and hasattr(request.user, 'company'):
                kwargs["queryset"] = Company.objects.filter(id=request.user.company.id)
        elif db_field.name == "created_by":
            # Restrict user choices
            kwargs["queryset"] = get_user_model().objects.filter(
                is_active=True
            ).order_by('username')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Set created_by user when creating new account"""
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)