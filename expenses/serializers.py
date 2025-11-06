from rest_framework import serializers
from .models import Expense, ExpenseHead, ExpenseSubHead
from accounts.models import Account

class ExpenseHeadSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)


    class Meta:
        model = ExpenseHead
        fields = ['id', 'name', 'company', 'company_name','is_active']
        extra_kwargs = {
            'company': {'required': True}
        }
class ExpenseSubHeadSerializer(serializers.ModelSerializer):
    head_name = serializers.StringRelatedField(source='head.name', read_only=True)
    head = serializers.PrimaryKeyRelatedField(queryset=ExpenseHead.objects.all())
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = ExpenseSubHead
        fields = ['id', 'name', 'head', 'head_name', 'company','is_active', 'company_name']  # ✅ include is_active

class ExpenseSerializer(serializers.ModelSerializer):
    head = serializers.PrimaryKeyRelatedField(queryset=ExpenseHead.objects.all())
    subhead = serializers.PrimaryKeyRelatedField(queryset=ExpenseSubHead.objects.all(), required=False, allow_null=True)
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=False, allow_null=True)
    head_name = serializers.CharField(source='head.name', read_only=True)
    subhead_name = serializers.CharField(source='subhead.name', read_only=True, allow_null=True)
    account_name = serializers.CharField(source='account.ac_name', read_only=True, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'company', 'head', 'subhead', 'head_name', 'subhead_name',
             'amount', 'payment_method', 'account', 'account_name',
            'expense_date', 'note', 'created_at', 'created_by', 'date_created',
            'invoice_number'  # Add invoice number
        ]
        read_only_fields = ['created_by', 'date_created', 'created_at', 'invoice_number']