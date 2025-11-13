# expenses/serializers.py
from rest_framework import serializers
from .models import Expense, ExpenseHead, ExpenseSubHead
from django.core.exceptions import ValidationError

class ExpenseHeadSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = ExpenseHead
        fields = ['id', 'name', 'company', 'created_by', 'date_created', 'is_active', 'status']

class ExpenseSubHeadSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source='head.name', read_only=True)
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = ExpenseSubHead
        fields = ['id', 'name', 'head', 'head_name', 'company', 'created_by', 'date_created', 'is_active', 'status']

class ExpenseSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source='head.name', read_only=True)
    subhead_name = serializers.CharField(source='subhead.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    expense_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Expense
        fields = [
            'id', 'invoice_number', 'head', 'head_name', 'subhead', 'subhead_name',
            'amount', 'payment_method', 'account', 'account_name', 'expense_date',
            'note', 'description', 'status', 'created_by', 'created_by_name',
            'date_created', 'company', 'expense_summary'
        ]
        read_only_fields = ['invoice_number', 'date_created', 'created_by']
    
    def get_expense_summary(self, obj):
        return obj.get_expense_summary()

class ExpenseCreateSerializer(serializers.ModelSerializer):
    """Serializer specifically for creating expenses"""
    
    class Meta:
        model = Expense
        fields = [
            'head', 'subhead', 'amount', 'payment_method', 'account',
            'expense_date', 'note', 'company'
        ]
    
    def validate_payment_method(self, value):
        """Convert payment method to lowercase to match choices"""
        if value:
            value = value.lower().strip()
            valid_choices = ['cash', 'bank', 'mobile', 'card', 'other']
            if value not in valid_choices:
                # Try to map common variations
                payment_mapping = {
                    'cash': 'cash',
                    'Cash': 'cash',
                    'CASH': 'cash',
                    'bank': 'bank',
                    'Bank': 'bank',
                    'BANK': 'bank',
                    'mobile': 'mobile',
                    'Mobile': 'mobile',
                    'MOBILE': 'mobile',
                    'card': 'card',
                    'Card': 'card',
                    'CARD': 'card',
                    'other': 'other',
                    'Other': 'other',
                    'OTHER': 'other'
                }
                if value in payment_mapping:
                    return payment_mapping[value]
                else:
                    raise serializers.ValidationError(
                        f"'{value}' is not a valid choice. Must be one of: {', '.join(valid_choices)}"
                    )
        return value
    
    def validate(self, data):
        # Validate that account has sufficient balance
        account = data.get('account')
        amount = data.get('amount')
        
        if account and amount and amount > account.balance:
            raise serializers.ValidationError({
                'amount': f'Insufficient balance in account. Available: {account.balance}'
            })
        
        return data
    
    def create(self, validated_data):
        # Set created_by from request context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)

class ExpenseUpdateSerializer(serializers.ModelSerializer):
    """Serializer specifically for updating expenses"""
    
    class Meta:
        model = Expense
        fields = [
            'head', 'subhead', 'amount', 'payment_method', 'account',
            'expense_date', 'note'
        ]
    
    def validate_payment_method(self, value):
        """Convert payment method to lowercase to match choices"""
        if value:
            value = value.lower().strip()
            valid_choices = ['cash', 'bank', 'mobile', 'card', 'other']
            if value not in valid_choices:
                # Try to map common variations
                payment_mapping = {
                    'cash': 'cash',
                    'Cash': 'cash',
                    'CASH': 'cash',
                    'bank': 'bank',
                    'Bank': 'bank',
                    'BANK': 'bank',
                    'mobile': 'mobile',
                    'Mobile': 'mobile',
                    'MOBILE': 'mobile',
                    'card': 'card',
                    'Card': 'card',
                    'CARD': 'card',
                    'other': 'other',
                    'Other': 'other',
                    'OTHER': 'other'
                }
                if value in payment_mapping:
                    return payment_mapping[value]
                else:
                    raise serializers.ValidationError(
                        f"'{value}' is not a valid choice. Must be one of: {', '.join(valid_choices)}"
                    )
        return value
    
    def validate(self, data):
        # Validate that account has sufficient balance
        account = data.get('account')
        amount = data.get('amount')
        
        if account and amount and amount > account.balance:
            raise serializers.ValidationError({
                'amount': f'Insufficient balance in account. Available: {account.balance}'
            })
        
        return data