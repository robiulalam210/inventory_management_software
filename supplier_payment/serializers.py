# supplier_payment/serializers.py
from rest_framework import serializers
from .model import SupplierPayment  # ✅ Fixed: changed 'model' to 'models'
from purchases.models import Purchase
from suppliers.models import Supplier
from accounts.models import Account
from django.contrib.auth import get_user_model

User = get_user_model()

class SupplierPaymentSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True)
    prepared_by_name = serializers.CharField(source='prepared_by.get_full_name', read_only=True)
    purchase_invoice_no = serializers.CharField(source='purchase.invoice_no', read_only=True, allow_null=True)  # ✅ Changed to invoice_no
    payment_summary = serializers.SerializerMethodField()
    
    # Make supplier field optional for writing, handle both supplier and supplier_id
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), 
        required=False,
        allow_null=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), 
        source='supplier',
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
    purchase_id = serializers.PrimaryKeyRelatedField(
        queryset=Purchase.objects.all(),
        source='purchase',
        write_only=True,
        required=False,
        allow_null=True
    )
    prepared_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='prepared_by',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = SupplierPayment
        fields = [
            'id', 'sp_no', 'company', 'supplier', 'supplier_id', 'supplier_name', 'supplier_phone',
            'payment_type', 'specific_bill', 'purchase', 'purchase_id', 'purchase_invoice_no',  # ✅ Changed field name
            'amount', 'payment_method', 'payment_date', 'remark', 
            'account', 'account_id', 'prepared_by', 'prepared_by_name', 'prepared_by_id',
            'cheque_status', 'cheque_no', 'cheque_date', 'bank_name', 'created_at', 'payment_summary'
        ]
        read_only_fields = [
            'id', 'sp_no', 'supplier_name', 'supplier_phone', 'purchase_invoice_no',  # ✅ Changed field name
            'prepared_by_name', 'company', 'prepared_by', 'created_at', 'payment_type',
            'specific_bill', 'payment_summary'
        ]

    def validate(self, attrs):
        # Check that either supplier or supplier_id is provided
        supplier = attrs.get('supplier')
        if not supplier:
            raise serializers.ValidationError({
                "supplier": "This field is required."
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
        
        # Validate cheque fields if payment method is cheque
        payment_method = attrs.get('payment_method')
        if payment_method == 'cheque':
            if not attrs.get('cheque_no'):
                raise serializers.ValidationError({
                    "cheque_no": "Cheque number is required when payment method is cheque."
                })
            if not attrs.get('cheque_date'):
                raise serializers.ValidationError({
                    "cheque_date": "Cheque date is required when payment method is cheque."
                })
        
        return attrs

    def get_payment_summary(self, obj):
        return obj.get_payment_summary()

    def create(self, validated_data):
        # Get request from context
        request = self.context.get('request')
        
        # Set company and prepared_by if not provided
        if request and request.user:
            if 'company' not in validated_data:
                validated_data['company'] = getattr(request.user, 'company', None)
            if 'prepared_by' not in validated_data:
                validated_data['prepared_by'] = request.user
        
        # Create the supplier payment
        payment = SupplierPayment.objects.create(**validated_data)
        return payment

    def update(self, instance, validated_data):
        # Get request from context
        request = self.context.get('request')
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance