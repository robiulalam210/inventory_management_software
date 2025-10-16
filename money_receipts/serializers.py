from rest_framework import serializers
from .models import MoneyReceipt
from sales.models import Sale
from customers.models import Customer
from accounts.models import Account
class MoneyReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)
    sale_invoice_no = serializers.CharField(source='sale.invoice_no', read_only=True, allow_null=True)
    payment_summary = serializers.SerializerMethodField()
    
    # Make customer field optional for writing, handle both customer and customer_id
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), 
        required=False,
        allow_null=True
    )
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
            'payment_type', 'specific_invoice', 'sale', 'sale_id', 'sale_invoice_no',
            'amount', 'payment_method', 'payment_date', 'remark', 
            'account', 'account_id', 'seller', 'seller_name',
            'cheque_status', 'cheque_id', 'created_at', 'payment_summary'
        ]
        read_only_fields = [
            'mr_no', 'customer_name', 'customer_phone', 'sale_invoice_no', 
            'seller_name', 'company', 'seller', 'created_at', 'payment_type',
            'specific_invoice', 'payment_summary'
        ]

    def validate(self, attrs):
        # Check that either customer or customer_id is provided
        customer = attrs.get('customer')
        if not customer:
            raise serializers.ValidationError({
                "customer": "This field is required."
            })
        
        # Validate payment amount
        amount = attrs.get('amount')
        if amount <= 0:
            raise serializers.ValidationError({
                "amount": "Payment amount must be greater than 0."
            })
        
        return attrs

    def get_payment_summary(self, obj):
        return obj.get_payment_summary()

    def create(self, validated_data):
        # Get request from context
        request = self.context.get('request')
        
        # Set company and seller
        if request and request.user:
            validated_data['company'] = getattr(request.user, 'company', None)
            validated_data['seller'] = request.user
        
        # Create the money receipt
        receipt = MoneyReceipt.objects.create(**validated_data)
        return receipt