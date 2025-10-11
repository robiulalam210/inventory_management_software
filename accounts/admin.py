from django.contrib import admin
from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ac_type', 'number', 'balance')
    list_filter = ('ac_type',)
    search_fields = ('name', 'number', 'bank_name', 'branch')