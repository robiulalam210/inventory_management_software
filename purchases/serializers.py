# branch_warehouse/serializers.py - MINIMAL FIXES ONLY

import logging
import traceback
from rest_framework import serializers
from .models import Purchase, PurchaseItem
from products.models import Product
from accounts.models import Account
from django.db import transaction as db_transaction
from decimal import Decimal

logger = logging.getLogger(__name__)


class PurchaseItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='subtotal')

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product_id', 'product_name', 'qty', 'price', 'discount', 'discount_type', 'product_total']
        read_only_fields = ['id', 'product_name', 'product_total']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value

    def validate_qty(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value


class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    purchase_items = PurchaseItemSerializer(many=True, write_only=True, required=False)
    items = PurchaseItemSerializer(many=True, read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False, write_only=True
    )
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    # Payment fields
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Purchase date
    purchase_date = serializers.DateField(required=True)
    
    # Instant pay field
    instant_pay = serializers.BooleanField(write_only=True, default=False)
    
    # Additional fields from request
    delivery_charge = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False, default=0,
        source='overall_delivery_charge'
    )
    service_charge = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False, default=0,
        source='overall_service_charge'
    )
    sub_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='total')
    
    # Charge type fields
    overall_service_type = serializers.CharField(
        write_only=True, required=False, default='fixed', 
        source='overall_service_charge_type'
    )
    overall_delivery_type = serializers.CharField(
        write_only=True, required=False, default='fixed', 
        source='overall_delivery_charge_type'
    )

    class Meta:
        model = Purchase
        fields = [
            'id', 'company', 'supplier', 'supplier_name', 'purchase_date', 'total', 'grand_total',
            'paid_amount', 'due_amount', 'change_amount', 'instant_pay',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_charge_type',
            'overall_service_charge', 'overall_service_charge_type',
            'vat', 'vat_type', 'invoice_no', 'payment_status', 'return_amount',
            'account_id', 'account_name', 'payment_method', 'remark',
            'purchase_items', 'items', 'delivery_charge', 'service_charge',
            'sub_total', 'overall_service_type', 'overall_delivery_type'
        ]
        read_only_fields = [
            'id', 'company', 'total', 'grand_total', 'invoice_no', 'payment_status',
            'due_amount', 'change_amount', 'supplier_name', 'account_name', 'sub_total'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        
        account = attrs.get('account')
        
        if 'account' in attrs and not account:
            attrs['account'] = None
        
        # Validate purchase items for creation
        if request and getattr(request, "method", None) == 'POST':
            purchase_items = attrs.get('purchase_items') or []
            if not purchase_items:
                raise serializers.ValidationError({"purchase_items": "At least one purchase item is required."})
            
            for i, item_data in enumerate(purchase_items):
                product = item_data.get('product')
                price = item_data.get('price', 0)
                qty = item_data.get('qty', 0)
                
                if not product:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Product is required."
                    })
                
                if price <= 0:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Price must be greater than 0 for product '{product.name}'."
                    })
                
                if qty <= 0:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Quantity must be greater than 0 for product '{product.name}'."
                    })
        
        # Validate instant payment requirements
        instant_pay = attrs.get('instant_pay', False)
        if instant_pay:
            if not attrs.get('payment_method'):
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required for instant payment."
                })
            if not attrs.get('account'):
                raise serializers.ValidationError({
                    "account": "Account is required for instant payment."
                })
        
        # Validate amounts
        overall_discount = attrs.get('overall_discount', 0)
        if overall_discount < 0:
            raise serializers.ValidationError({
                "overall_discount": "Discount cannot be negative."
            })
        
        delivery_charge = attrs.get('overall_delivery_charge', 0)
        service_charge = attrs.get('overall_service_charge', 0)
        vat = attrs.get('vat', 0)
        
        if delivery_charge < 0:
            raise serializers.ValidationError({"delivery_charge": "Delivery charge cannot be negative."})
        if service_charge < 0:
            raise serializers.ValidationError({"service_charge": "Service charge cannot be negative."})
        if vat < 0:
            raise serializers.ValidationError({"vat": "VAT cannot be negative."})
        
        return attrs

    def create(self, validated_data):
        try:
            request = self.context.get('request')
            user = request.user if request else None
            
            if not user or not hasattr(user, 'company') or not user.company:
                raise serializers.ValidationError({"error": "User does not belong to a company."})

            items_data = validated_data.pop('purchase_items', [])
            instant_pay = validated_data.pop('instant_pay', False)
            
            account = validated_data.get('account', None)
            payment_method = validated_data.get('payment_method', None)
            paid_amount = validated_data.get('paid_amount', Decimal('0.00'))
            
            validated_data['company'] = user.company
            validated_data['created_by'] = user

            with db_transaction.atomic():
                # Create purchase first (without items)
                purchase = Purchase.objects.create(**validated_data)
                
                # Create purchase items
                for item_data in items_data:
                    PurchaseItem.objects.create(purchase=purchase, **item_data)

                # Update totals to calculate the actual totals
                purchase.update_totals(force_update=True)
                
                # Handle payments properly
                if instant_pay and account and payment_method:
                    if paid_amount > 0:
                        try:
                            purchase.make_payment(
                                amount=paid_amount,
                                payment_method=payment_method,
                                account=account,
                                description=f"Instant payment for purchase {purchase.invoice_no}"
                            )
                        except Exception as e:
                            logger.error(f"ERROR: Failed to apply instant payment: {str(e)}")
                    elif purchase.due_amount > 0:
                        try:
                            purchase.make_payment(
                                amount=purchase.due_amount,
                                payment_method=payment_method,
                                account=account,
                                description=f"Full payment for purchase {purchase.invoice_no}"
                            )
                        except Exception as e:
                            logger.error(f"ERROR: Failed to apply full payment: {str(e)}")
                elif paid_amount > 0 and account and payment_method:
                    try:
                        purchase.make_payment(
                            amount=paid_amount,
                            payment_method=payment_method,
                            account=account,
                            description=f"Partial payment for purchase {purchase.invoice_no}"
                        )
                    except Exception as e:
                        logger.error(f"ERROR: Failed to apply payment: {str(e)}")

            return purchase
            
        except serializers.ValidationError as e:
            raise e
        except Exception as e:
            logger.exception("ERROR: Exception in PurchaseSerializer.create")
            raise serializers.ValidationError({
                "error": f"Failed to create purchase: {str(e)}"
            })

    def to_representation(self, instance):
        """Custom representation to include calculated fields"""
        representation = super().to_representation(instance)
        
        # Force update totals to ensure calculations are current
        try:
            instance.update_totals(force_update=True)
        except Exception as e:
            logger.error(f"ERROR: Failed to update totals in to_representation: {str(e)}")
        
        # Add payment breakdown with fresh data
        try:
            representation['payment_breakdown'] = instance.get_payment_breakdown()
        except Exception as e:
            logger.error(f"ERROR: Failed to get payment breakdown: {str(e)}")
            representation['payment_breakdown'] = {}
        
        # Ensure all calculated fields are included
        representation['grand_total'] = float(instance.grand_total)
        representation['total'] = float(instance.total)
        representation['due_amount'] = float(instance.due_amount)
        representation['paid_amount'] = float(instance.paid_amount)
        representation['change_amount'] = float(instance.change_amount)
        
        # Add item count and total quantity
        representation['item_count'] = instance.item_count
        representation['total_quantity'] = instance.total_quantity
        
        return representation