from django.contrib import admin
from .models import Income, IncomeHead

@admin.register(IncomeHead)
class IncomeHeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active')

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'company', 'head', 'amount', 'account', 'income_date')
    search_fields = ('invoice_number', 'note')