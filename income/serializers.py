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

class IncomeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Income with account validation"""
    class Meta:
        model = Income
        fields = ['head', 'amount', 'account', 'income_date', 'note', 'company']

    def validate(self, data):
        account = data.get('account')
        amount = data.get('amount')
        if account and amount and amount <= 0:
            raise serializers.ValidationError({'amount': 'Income amount must be > 0'})
        # You could add company-account match check here if needed.
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)