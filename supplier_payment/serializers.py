from rest_framework import serializers
from .model import SupplierPayment
from purchases.models import Purchase
from suppliers.models import Supplier
from accounts.models import Account

from django.contrib.auth import get_user_model

User = get_user_model()

class SupplierPaymentSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True)
    prepared_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    purchase_invoice_no = serializers.CharField(source='purchase.invoice_no', read_only=True, allow_null=True)
    payment_summary = serializers.SerializerMethodField()
    
    # Input fields
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=True)
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=True)
    purchase = serializers.PrimaryKeyRelatedField(queryset=Purchase.objects.all(), required=False, allow_null=True)
    created_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)

    class Meta:
        model = SupplierPayment
        fields = [
            'id', 'sp_no', 'company', 'supplier', 'supplier_name', 'supplier_phone',
            'payment_type', 'use_advance', 'advance_amount_used', 'purchase', 'purchase_invoice_no',
            'amount', 'payment_method', 'payment_date', 'description', 
            'account', 'created_by', 'prepared_by_name', 'reference_no', 'status',
            'created_at', 'updated_at', 'payment_summary'
        ]
        read_only_fields = [
            'id', 'sp_no', 'supplier_name', 'supplier_phone', 'purchase_invoice_no',
            'prepared_by_name', 'company', 'created_at', 'updated_at', 'status',
            'payment_summary'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        
        # Ensure supplier is provided
        if 'supplier' not in attrs:
            raise serializers.ValidationError({
                "supplier": "Supplier is required."
            })
            
        # Ensure account is provided
        if 'account' not in attrs:
            raise serializers.ValidationError({
                "account": "Account is required."
            })
        
        # Validate payment amount
        amount = attrs.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError({
                "amount": "Payment amount must be greater than 0."
            })
        
        # Validate payment date
        payment_date = attrs.get('payment_date')
        if not payment_date:
            raise serializers.ValidationError({
                "payment_date": "Payment date is required."
            })
        
        return attrs

    def get_payment_summary(self, obj):
        return obj.get_payment_summary()

    def create(self, validated_data):
        request = self.context.get('request')
        
        # Set company from request user
        if request and request.user:
            validated_data['company'] = getattr(request.user, 'company', None)
            
        # Set created_by from request user if not provided
        if 'created_by' not in validated_data and request and request.user:
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)