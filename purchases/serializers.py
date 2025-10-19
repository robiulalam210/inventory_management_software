from itertools import product
import logging
import traceback
from rest_framework import serializers
from .models import Purchase, PurchaseItem
from products.models import Product
from accounts.models import Account
from django.db import transaction
from decimal import Decimal

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product_id', 'product_name', 'qty', 'price', 'discount', 'discount_type']
        read_only_fields = ['id', 'product_name']

class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.SerializerMethodField()
    purchase_items = PurchaseItemSerializer(many=True, write_only=True, required=False)
    items = PurchaseItemSerializer(many=True, read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    # Add write-only fields for mapping from Flutter request
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)

    class Meta:
        model = Purchase
        fields = [
            'id', 'company', 'supplier', 'supplier_name', 'total', 'grand_total', 'date',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_charge_type',
            'overall_service_charge', 'overall_service_charge_type',
            'vat', 'vat_type', 'invoice_no', 'payment_status', 'return_amount',
            'account_id', 'account_name', 'payment_method',
            'purchase_items', 'items', 'delivery_charge', 'service_charge'  # Added new fields
        ]
        read_only_fields = ['company', 'total', 'grand_total', 'invoice_no']

    def get_supplier_name(self, obj):
        try:
            return obj.supplier.name if obj.supplier else None
        except AttributeError:
            return None

    def validate(self, attrs):
        request = self.context.get('request')
        if request and getattr(request, "method", None) == 'POST':
            purchase_items = attrs.get('purchase_items') or []
            if not purchase_items:
                raise serializers.ValidationError("At least one purchase item is required.")
        return attrs

    def create(self, validated_data):
        logger = logging.getLogger(__name__)
        try:
            request = self.context.get('request')
            if not request or not hasattr(request.user, 'company') or not request.user.company:
                raise serializers.ValidationError("User does not belong to a company.")

            # Extract and map write-only fields
            delivery_charge = validated_data.pop('delivery_charge', 0)
            service_charge = validated_data.pop('service_charge', 0)
            items_data = validated_data.pop('purchase_items', [])
            
            # Map to model fields
            validated_data['overall_delivery_charge'] = delivery_charge
            validated_data['overall_service_charge'] = service_charge

            validated_data['company'] = request.user.company
            account = validated_data.get('account', None)

            with transaction.atomic():
                purchase = Purchase.objects.create(**validated_data)

                # Create purchase items
                for item_data in items_data:
                    product = item_data['product']
                    if getattr(product, 'company', None) != request.user.company:
                        raise serializers.ValidationError({
                            "purchase_items": [f"Product '{getattr(product, 'name', product)}' does not belong to your company."]
                        })
                    qty = item_data['qty']
                    purchase_item = PurchaseItem.objects.create(purchase=purchase, **item_data)
                    product.stock_qty = (getattr(product, 'stock_qty', 0) or 0) + qty
                    product.save(update_fields=['stock_qty'])

                # Use the model's update_totals method for consistent calculation
                purchase.update_totals()

                # Update account balance (optional, for cash outflow)
                if account and purchase.grand_total > 0:
                    account.balance -= Decimal(str(purchase.grand_total))
                    account.save(update_fields=['balance'])

            return purchase
        except Exception as e:
            logger.exception("Exception in PurchaseSerializer.create")
            tb = traceback.format_exc()
            raise serializers.ValidationError({
                "error": f"Internal error: {e}",
                "traceback": tb
            })