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
    company_name = serializers.CharField(source='company.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'company', 'company_name', 'head', 'subhead', 'head_name', 'subhead_name',
            'amount', 'payment_method', 'account', 'account_name',
            'expense_date', 'note', 'date_created', 'created_by', 'created_by_name',
            'invoice_number', 'status', 'description'  # Add the computed properties
        ]
        read_only_fields = ['created_by', 'date_created', 'invoice_number', 'company_name', 'created_by_name']

    def validate(self, data):
        """
        Custom validation for expense data
        """
        # Validate that subhead belongs to the selected head
        head = data.get('head')
        subhead = data.get('subhead')
        
        if subhead and head and subhead.head != head:
            raise serializers.ValidationError({
                'subhead': 'This subhead does not belong to the selected expense head.'
            })
        
        # Validate amount is positive
        amount = data.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError({
                'amount': 'Amount must be greater than zero.'
            })
        
        return data

    def create(self, validated_data):
        """
        Create expense with automatic invoice number generation
        """
        # The invoice_number will be automatically generated in the model's save method
        return super().create(validated_data)