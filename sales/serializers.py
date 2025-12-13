# sales/serializers.py - COMPLETE FIXED VERSION

from rest_framework import serializers
from .models import Sale, SaleItem
from products.models import Product
from accounts.models import Account
from customers.models import Customer
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class SaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_id', 'product_name', 'quantity', 'unit_price',
            'discount', 'discount_type', 'subtotal'
        ]
        read_only_fields = ['id', 'product_name', 'subtotal']

    def get_subtotal(self, obj):
        return float(obj.subtotal()) if obj.subtotal() else 0.0


class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account',
        required=False,
        allow_null=True
    )
    account_name = serializers.CharField(source='account.name', read_only=True)
    sale_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    sale_by_name = serializers.CharField(source='sale_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    items = SaleItemSerializer(many=True, write_only=True)
    
    # Additional fields for receiving charge data
    vat = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    
    # Read-only fields for calculated values
    gross_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)
    invoice_no = serializers.CharField(read_only=True)
    sale_date = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'customer_type',
            'sale_type', 'sale_date', 'sale_by', 'sale_by_name', 'created_by_name',
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'paid_amount', 'due_amount', 'change_amount',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'with_money_receipt', 'remark', 'items', 'payment_status',
            # Additional fields from request
            'vat', 'service_charge', 'delivery_charge'
        ]
        read_only_fields = [
            'id', 'invoice_no', 'sale_date', 'payment_status',
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'due_amount', 'change_amount', 'created_by_name', 'sale_by_name',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount'
        ]

    def validate(self, attrs):
        """Validate sale data"""
        customer_type = attrs.get('customer_type', 'walk_in')
        paid_amount = attrs.get('paid_amount', Decimal('0.00'))
        items = attrs.get('items', [])
        payment_method = attrs.get('payment_method')
        account = attrs.get('account')
        
        # Validate items
        if not items:
            raise serializers.ValidationError({'items': 'At least one item is required.'})
        
        # Validate customer
        if customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({'customer': 'Saved customer must have a record.'})
        
        # Validate payment
        if paid_amount and paid_amount > 0:
            if not payment_method:
                raise serializers.ValidationError({
                    'payment_method': 'Payment method is required when making a payment.'
                })
            if not account:
                raise serializers.ValidationError({
                    'account': 'Account is required when making a payment.'
                })
        
        return attrs

    def create(self, validated_data):
        """Create sale with items"""
        items_data = validated_data.pop('items', [])
        
        # Extract and map charge fields
        vat = validated_data.pop('vat', Decimal('0.00'))
        service_charge = validated_data.pop('service_charge', Decimal('0.00'))
        delivery_charge = validated_data.pop('delivery_charge', Decimal('0.00'))
        
        # Map to model fields
        validated_data['overall_vat_amount'] = vat
        validated_data['overall_service_charge'] = service_charge
        validated_data['overall_delivery_charge'] = delivery_charge
        
        # Set charge types to 'fixed'
        validated_data['overall_vat_type'] = 'fixed'
        validated_data['overall_service_type'] = 'fixed'
        validated_data['overall_delivery_type'] = 'fixed'
        
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            if 'sale_by' not in validated_data or not validated_data['sale_by']:
                validated_data['sale_by'] = request.user
            if hasattr(request.user, 'company'):
                validated_data['company'] = request.user.company
        
        # Handle walk-in customer
        if validated_data.get('customer_type') == 'walk_in':
            validated_data['customer'] = None
            if not validated_data.get('customer_name'):
                validated_data['customer_name'] = "Walk-in Customer"
        
        with transaction.atomic():
            # Create sale
            sale = Sale.objects.create(**validated_data)
            
            # Create sale items
            sale_items = []
            for item_data in items_data:
                sale_items.append(SaleItem(
                    sale=sale,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    discount=item_data.get('discount', Decimal('0.00')),
                    discount_type=item_data.get('discount_type', 'fixed')
                ))
            
            SaleItem.objects.bulk_create(sale_items)
            
            # Calculate totals
            sale.calculate_totals()
            
            # Handle payment if any
            if sale.paid_amount > 0 and sale.account:
                try:
                    sale.account.balance += sale.paid_amount
                    sale.account.save(update_fields=['balance'])
                    logger.info(f"Account {sale.account.name} balance updated")
                except Exception as e:
                    logger.error(f"Error updating account balance: {e}")
            
            # Refresh to get all calculated values
            sale.refresh_from_db()
            
            return sale

    def to_representation(self, instance):
        """Convert sale to representation with proper formatting"""
        rep = super().to_representation(instance)
        
        # Add items data
        rep['items'] = SaleItemSerializer(instance.items.all(), many=True).data
        
        # Ensure customer name is correct
        rep['customer_name'] = instance.get_customer_display()
        
        # Format decimal fields as float for JSON
        decimal_fields = [
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'paid_amount', 'due_amount', 'change_amount',
            'overall_discount', 'overall_delivery_charge',
            'overall_service_charge', 'overall_vat_amount'
        ]
        
        for field in decimal_fields:
            if field in rep and rep[field] is not None:
                rep[field] = float(rep[field])
        
        return rep