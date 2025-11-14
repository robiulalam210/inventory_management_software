from rest_framework import serializers
from .models import Transaction
from accounts.models import Account
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta

# transactions/serializers.py
class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_type = serializers.CharField(source='account.ac_type', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    # Sale related
    sale_invoice_no = serializers.CharField(source='sale.invoice_no', read_only=True, allow_null=True)
    
    # Money receipt related
    money_receipt_no = serializers.CharField(source='money_receipt.mr_no', read_only=True, allow_null=True)
    
    # Expense related - FIXED FIELD NAMES
    expense_invoice_number = serializers.CharField(source='expense.invoice_number', read_only=True, allow_null=True)
    expense_head = serializers.CharField(source='expense.head.name', read_only=True, allow_null=True)
    
    # Purchase related
    purchase_invoice_no = serializers.CharField(source='purchase.invoice_no', read_only=True, allow_null=True)
    
    # Supplier payment related
    supplier_payment_reference = serializers.CharField(source='supplier_payment.reference_no', read_only=True, allow_null=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_no', 'transaction_type', 'amount', 
            'account', 'account_name', 'account_type', 'payment_method',
            'cheque_no', 'reference_no', 'transaction_date', 'status',
            'description', 
            
            # Related objects
            'sale', 'sale_invoice_no',
            'money_receipt', 'money_receipt_no',
            'expense', 'expense_invoice_number', 'expense_head',  # Updated fields
            'purchase', 'purchase_invoice_no',
            'supplier_payment', 'supplier_payment_reference',
            
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