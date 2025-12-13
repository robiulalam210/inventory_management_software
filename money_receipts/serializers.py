# money_receipts/serializers.py - COMPLETE FIXED VERSION

from rest_framework import serializers
from .models import MoneyReceipt
from sales.models import Sale
from customers.models import Customer
from accounts.models import Account
from django.contrib.auth import get_user_model

User = get_user_model()

class MoneyReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    seller_name = serializers.CharField(source='seller.username', read_only=True)
    sale_invoice_no = serializers.CharField(source='sale.invoice_no', read_only=True, allow_null=True)
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    payment_summary = serializers.SerializerMethodField()
    
    # Writeable fields
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), 
        source='customer',
        write_only=True,
        required=False,
        allow_null=True
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account', 
        write_only=True,
        required=False,
        allow_null=True
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(),
        source='sale',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = MoneyReceipt
        fields = [
            'id', 'mr_no', 'company', 'customer', 'customer_id', 'customer_name', 'customer_phone',
            'payment_type', 'specific_invoice', 'is_advance_payment', 'sale', 'sale_id', 'sale_invoice_no',
            'amount', 'payment_method', 'payment_date', 'remark', 
            'account', 'account_id', 'account_name', 'seller', 'seller_name',
            'cheque_status', 'cheque_id', 'payment_status', 'created_at', 'updated_at', 'payment_summary'
        ]
        read_only_fields = [
            'id', 'mr_no', 'customer_name', 'customer_phone', 'sale_invoice_no', 
            'seller_name', 'account_name', 'company', 'created_at', 'updated_at',
            'payment_type', 'specific_invoice', 'payment_summary'
        ]

    def __init__(self, *args, **kwargs):
        """Initialize with company-filtered querysets"""
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            company = request.user.company
            
            # Filter querysets by company
            self.fields['customer_id'].queryset = Customer.objects.filter(company=company)
            self.fields['account_id'].queryset = Account.objects.filter(company=company)
            self.fields['sale_id'].queryset = Sale.objects.filter(company=company)

    def validate(self, attrs):
        """Enhanced validation with company checks"""
        request = self.context.get('request')
        company = getattr(request.user, 'company', None) if request else None
        
        amount = attrs.get('amount')
        customer = attrs.get('customer')
        sale = attrs.get('sale')
        account = attrs.get('account')  # SUCCESS: FIXED: Changed from 'attts' to 'attrs'
        is_advance_payment = attrs.get('is_advance_payment', False)
        payment_type = attrs.get('payment_type', 'overall')

        # Validate amount
        if not amount or amount <= 0:
            raise serializers.ValidationError({
                "amount": "Payment amount must be greater than 0."
            })

        # SUCCESS: FIXED: Validate company consistency
        if company:
            if customer and customer.company != company:
                raise serializers.ValidationError({
                    "customer": "Customer must belong to your company."
                })
            
            if sale and sale.company != company:
                raise serializers.ValidationError({
                    "sale": "Sale must belong to your company."
                })
            
            if account and account.company != company:
                raise serializers.ValidationError({
                    "account": "Account must belong to your company."
                })

        # Validate customer requirements
        if is_advance_payment and not customer:
            raise serializers.ValidationError({
                "customer": "Customer is required for advance payments."
            })

        if payment_type == 'specific' and not sale:
            raise serializers.ValidationError({
                "sale": "Sale is required for specific invoice payments."
            })

        if payment_type == 'overall' and not customer:
            raise serializers.ValidationError({
                "customer": "Customer is required for overall payments."
            })

        return attrs

    def create(self, validated_data):
        """Create money receipt with proper context"""
        request = self.context.get('request')
        
        if not request or not hasattr(request.user, 'company'):
            raise serializers.ValidationError("User must be associated with a company.")
        
        # SUCCESS: FIXED: Ensure company is set from request user
        validated_data['company'] = request.user.company
        
        # Set seller and created_by from request user
        if 'seller' not in validated_data or not validated_data['seller']:
            validated_data['seller'] = request.user
        if 'created_by' not in validated_data or not validated_data['created_by']:
            validated_data['created_by'] = request.user
        
        # Set default payment method if not provided
        if 'payment_method' not in validated_data or not validated_data['payment_method']:
            validated_data['payment_method'] = 'cash'
        
        # SUCCESS: FIXED: Double-check customer company
        customer = validated_data.get('customer')
        if customer and customer.company != validated_data['company']:
            raise serializers.ValidationError("Customer company mismatch.")
        
        # Create the money receipt
        receipt = MoneyReceipt.objects.create(**validated_data)
        return receipt

    def get_payment_summary(self, obj):
        """Get payment summary from model method"""
        return obj.get_payment_summary()