from rest_framework import serializers
from .models import Transaction
from accounts.models import Account
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta

class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_type = serializers.CharField(source='account.ac_type', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    sale_invoice_no = serializers.CharField(source='sale.invoice_no', read_only=True)
    money_receipt_no = serializers.CharField(source='money_receipt.mr_no', read_only=True)
    expense_no = serializers.CharField(source='expense.expense_no', read_only=True)
    purchase_no = serializers.CharField(source='purchase.purchase_no', read_only=True)
    supplier_payment_no = serializers.CharField(source='supplier_payment.payment_no', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_no', 'transaction_type', 'amount', 
            'account', 'account_name', 'account_type', 'payment_method',
            'cheque_no', 'reference_no', 'transaction_date', 'status',
            'description', 
            'sale', 'sale_invoice_no', 
            'money_receipt', 'money_receipt_no',
            'expense', 'expense_no',
            'purchase', 'purchase_no',
            'supplier_payment', 'supplier_payment_no',
            'created_by', 'created_by_name',
            'created_at', 'updated_at', 'company'
        ]
        read_only_fields = ['transaction_no', 'created_at', 'updated_at']
    
    def validate(self, data):
        # Ensure account belongs to the same company
        account = data.get('account')
        company = data.get('company')
        
        if account and company and account.company != company:
            raise serializers.ValidationError({
                'account': 'Account must belong to the same company'
            })
        
        # Validate amount
        amount = data.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError({
                'amount': 'Amount must be greater than 0'
            })
        
        return data
    
    def create(self, validated_data):
        # Set created_by from request user
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)

class TransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'transaction_type', 'amount', 'account', 'payment_method',
            'cheque_no', 'reference_no', 'transaction_date', 'description',
            'sale', 'money_receipt', 'expense', 'purchase', 'supplier_payment', 'company'
        ]
    
    def validate(self, data):
        account = data.get('account')
        transaction_type = data.get('transaction_type')
        amount = data.get('amount')
        
        if transaction_type == 'debit' and account and amount > account.balance:
            raise serializers.ValidationError({
                'amount': 'Insufficient account balance'
            })
        
        return data

class AccountBalanceSerializer(serializers.ModelSerializer):
    current_balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_credits = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_debits = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    transaction_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'name', 'ac_type', 'ac_no', 'current_balance', 
            'total_credits', 'total_debits', 'transaction_count'
        ]

class TransactionSummarySerializer(serializers.Serializer):
    total_transactions = serializers.IntegerField()
    total_credits = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_debits = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_flow = serializers.DecimalField(max_digits=14, decimal_places=2)
    
    class Meta:
        fields = ['total_transactions', 'total_credits', 'total_debits', 'net_flow']