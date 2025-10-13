from django.contrib import admin
from .models import ExpenseHead, ExpenseSubHead, Expense

# Inline for subheads under heads
class ExpenseSubHeadInline(admin.TabularInline):
    model = ExpenseSubHead
    extra = 1  # How many empty forms to display

@admin.register(ExpenseHead)
class ExpenseHeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'company')
    inlines = [ExpenseSubHeadInline]

@admin.register(ExpenseSubHead)
class ExpenseSubHeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'head', 'company')
    list_filter = ('head', 'company')
    search_fields = ('name',)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'head', 'subhead', 'amount', 'account', 'expense_date', 'company')
    list_filter = ('head', 'subhead', 'account', 'company', 'expense_date', 'payment_method')
    search_fields = ('description',)
    date_hierarchy = 'expense_date'
