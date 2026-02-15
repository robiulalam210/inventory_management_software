from rest_framework import serializers
from .models import Income, IncomeHead

class IncomeHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeHead
        fields = ['id', 'name', 'company', 'created_by', 'date_created', 'is_active']

class IncomeSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source='head.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Income
        fields = [
            'id', 'invoice_number', 'head', 'head_name',
            'amount', 'account', 'account_name', 'income_date',
            'note', 'created_by', 'created_by_name', 'date_created', 'company'
        ]
        read_only_fields = ['invoice_number', 'date_created', 'created_by']