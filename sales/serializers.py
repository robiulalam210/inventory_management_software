# sales/serializers.py - COMPLETE FIXED VERSION

from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from products.models import Product
from accounts.models import Account
from money_receipts.models import MoneyReceipt
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

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
        return obj.subtotal()

    def validate(self, attrs):
        product = attrs.get('product')
        qty = attrs.get('quantity', 0)
        request = self.context.get('request')

        if not product:
            raise serializers.ValidationError({
                'product': 'Product is required.'
            })

        if qty <= 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity must be greater than 0.'
            })

        if qty > product.stock_qty:
            raise serializers.ValidationError({
                'quantity': f"Not enough stock for {product.name}. Available: {product.stock_qty}"
            })

        if request and hasattr(request.user, 'company') and product.company != request.user.company:
            raise serializers.ValidationError({
                'product': f"Cannot use product from another company: {product.company.name}"
            })

        return attrs


class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), 
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(required=False, allow_blank=True)
    items = SaleItemSerializer(many=True, write_only=True)  # ✅ FIXED: Make items write_only
    due_amount = serializers.SerializerMethodField()
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), 
        source='account', 
        allow_null=True, 
        required=False
    )
    account_name = serializers.CharField(source='account.name', read_only=True, required=False, allow_null=True)
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    sale_by_name = serializers.CharField(source='sale_by.username', read_only=True)
    
    vat = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    
    paid_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, 
        default=0,
        min_value=0
    )
    
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'sale_by_name', 'created_by_name',
            'gross_total', 'net_total', 'grand_total', 'payable_amount', 'paid_amount',
            'due_amount', 'change_amount', 'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'customer_type', 'with_money_receipt', 'remark',
            'vat', 'service_charge', 'delivery_charge',
            'items'  # ✅ This is now write_only
        ]
        read_only_fields = [
            'id', 'invoice_no', 'gross_total', 'net_total', 'grand_total', 
            'payable_amount', 'due_amount', 'change_amount',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount',
            'created_by_name', 'sale_by_name'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def validate(self, attrs):
        customer_type = attrs.get('customer_type', 'walk_in')
        with_money_receipt = attrs.get('with_money_receipt', 'No')
        paid_amount = attrs.get('paid_amount', 0)
        items = attrs.get('items', [])
        
        # Validate items exist
        if not items:
            raise serializers.ValidationError({
                'items': 'At least one item is required for the sale.'
            })
        
        # Remove customer requirement for walk-in with money receipt
        if customer_type == 'walk_in' and with_money_receipt == 'Yes':
            if not paid_amount or paid_amount <= 0:
                raise serializers.ValidationError({
                    'paid_amount': 'Walk-in customers with money receipt must provide payment amount.'
                })
        
        # Saved customers always need customer record
        if customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({
                'customer': 'Saved customers must have a customer record.'
            })
        
        return attrs

    def create(self, validated_data):
        """Create sale with nested items - FIXED VERSION"""
        try:
            # Extract nested items data
            items_data = validated_data.pop('items', [])
            
            # Extract additional fields
            vat_amount = validated_data.pop('vat', 0)
            service_charge_amount = validated_data.pop('service_charge', 0)
            delivery_charge_amount = validated_data.pop('delivery_charge', 0)
            
            validated_data['overall_vat_amount'] = vat_amount
            validated_data['overall_service_charge'] = service_charge_amount
            validated_data['overall_delivery_charge'] = delivery_charge_amount
            
            # Get request context
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['created_by'] = request.user
                validated_data['sale_by'] = request.user
                # Ensure company is set from user
                if hasattr(request.user, 'company'):
                    validated_data['company'] = request.user.company

            # Handle customer for walk-in sales
            customer = validated_data.get('customer')
            customer_type = validated_data.get('customer_type', 'walk_in')
            
            if customer_type == 'walk_in' and not customer:
                validated_data['customer'] = None
                if not validated_data.get('customer_name'):
                    validated_data['customer_name'] = 'Walk-in Customer'

            # Use transaction to ensure data consistency
            with transaction.atomic():
                # Create the sale instance
                sale = Sale.objects.create(**validated_data)

                # Create all sale items
                sale_items = []
                for item_data in items_data:
                    sale_item = SaleItem(
                        sale=sale,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        discount=item_data.get('discount', 0),
                        discount_type=item_data.get('discount_type', 'fixed')
                    )
                    sale_items.append(sale_item)
                
                # Bulk create items for better performance
                SaleItem.objects.bulk_create(sale_items)
                
                # Update sale totals
                sale.update_totals()
                
                # Handle account balance and money receipt
                account = validated_data.get('account')
                with_money_receipt = validated_data.get('with_money_receipt', 'No')
                
                if account and sale.paid_amount > 0:
                    try:
                        account.balance += sale.paid_amount
                        account.save(update_fields=['balance'])
                        
                        if with_money_receipt == 'Yes' and sale.paid_amount > 0:
                            try:
                                sale.create_money_receipt()
                            except Exception as e:
                                logger.error(f"Error creating money receipt: {e}")
                    except Exception as e:
                        logger.error(f"Error updating account balance: {e}")

                return sale

        except Exception as e:
            logger.error(f"Error creating sale: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise serializers.ValidationError(f"Failed to create sale: {str(e)}")

    def to_representation(self, instance):
        """Custom representation to include items in response"""
        representation = super().to_representation(instance)
        
        # Add items to the response
        items_serializer = SaleItemSerializer(instance.items.all(), many=True)
        representation['items'] = items_serializer.data
        
        representation['gross_total'] = instance.gross_total
        representation['net_total'] = instance.net_total
        representation['grand_total'] = instance.grand_total
        representation['payable_amount'] = instance.payable_amount
        representation['due_amount'] = instance.due_amount
        representation['change_amount'] = instance.change_amount
        
        if instance.customer:
            representation['customer_name'] = instance.customer.name
        else:
            representation['customer_name'] = 'Walk-in Customer'
            
        return representation


class DueSaleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    invoice_no = serializers.CharField(read_only=True)
    sale_date = serializers.DateTimeField(read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    due_amount = serializers.SerializerMethodField()
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_name', 'sale_date', 
            'grand_total', 'paid_amount', 'due_amount', 'payment_status'
        ]
    
    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)