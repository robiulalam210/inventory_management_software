import logging
import traceback
from rest_framework import serializers
from .models import Supplier, Purchase, PurchaseItem
from products.models import Product
from django.db import transaction

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

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
    items = PurchaseItemSerializer(many=True, read_only=True)  # <-- FIXED HERE

    class Meta:
        model = Purchase
        fields = [
            'id', 'company', 'supplier', 'supplier_name', 'total', 'date',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_charge_type',
            'overall_service_charge', 'overall_service_charge_type',
            'vat', 'vat_type', 'invoice_no', 'payment_status',
            'purchase_items', 'items'
        ]
        read_only_fields = ['company', 'total', 'invoice_no']

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

            validated_data['company'] = request.user.company
            items_data = validated_data.pop('purchase_items', [])

            with transaction.atomic():
                purchase = Purchase.objects.create(**validated_data)
                total_amount = 0

                for item_data in items_data:
                    product = item_data['product']
                    if getattr(product, 'company', None) != request.user.company:
                        raise serializers.ValidationError(
                            f"Cannot add product {getattr(product, 'name', product)} from another company ({getattr(product.company, 'name', None)})"
                        )
                    qty = item_data['qty']
                    purchase_item = PurchaseItem.objects.create(purchase=purchase, **item_data)
                    product.stock_qty = (getattr(product, 'stock_qty', 0) or 0) + qty
                    product.save(update_fields=['stock_qty'])
                    subtotal_func = getattr(purchase_item, 'subtotal', None)
                    subtotal = subtotal_func() if callable(subtotal_func) else (purchase_item.qty * purchase_item.price)
                    total_amount += float(subtotal)

                def safe_num(val): 
                    try:
                        return float(val or 0)
                    except Exception:
                        return 0

                # Defensive value assignments to avoid NoneType errors
                overall_discount = safe_num(getattr(purchase, 'overall_discount', 0))
                overall_discount_type = getattr(purchase, 'overall_discount_type', 'flat') or 'flat'
                overall_delivery_charge = safe_num(getattr(purchase, 'overall_delivery_charge', 0))
                overall_delivery_charge_type = getattr(purchase, 'overall_delivery_charge_type', 'flat') or 'flat'
                overall_service_charge = safe_num(getattr(purchase, 'overall_service_charge', 0))
                overall_service_charge_type = getattr(purchase, 'overall_service_charge_type', 'flat') or 'flat'
                vat = safe_num(getattr(purchase, 'vat', 0))
                vat_type = getattr(purchase, 'vat_type', 'flat') or 'flat'

                # Apply overall charges/discounts
                if overall_discount:
                    if overall_discount_type == 'percentage':
                        total_amount -= total_amount * (overall_discount / 100)
                    else:
                        total_amount -= overall_discount

                if overall_delivery_charge:
                    if overall_delivery_charge_type == 'percentage':
                        total_amount += total_amount * (overall_delivery_charge / 100)
                    else:
                        total_amount += overall_delivery_charge

                if overall_service_charge:
                    if overall_service_charge_type == 'percentage':
                        total_amount += total_amount * (overall_service_charge / 100)
                    else:
                        total_amount += overall_service_charge

                if vat:
                    if vat_type == 'percentage':
                        total_amount += total_amount * (vat / 100)
                    else:
                        total_amount += vat

                purchase.total = round(total_amount, 2)
                purchase.save(update_fields=['total'])

            return purchase
        except Exception as e:
            logger.exception("Exception in PurchaseSerializer.create")
            # Add traceback in the error detail (for development only!)
            tb = traceback.format_exc()
            raise serializers.ValidationError({
                "error": f"Internal error: {e}",
                "traceback": tb
            })