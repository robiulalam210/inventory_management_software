from rest_framework import serializers
from .models import Supplier, Purchase, PurchaseItem
from products.models import Product


# Supplier Serializer
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


# Purchase Item Serializer
class PurchaseItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source='product', queryset=Product.objects.all()
    )
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product_id', 'product_name', 'qty', 'price', 'discount', 'discount_type']

    def subtotal(self):
        qty = self.validated_data.get('qty', 0)
        price = self.validated_data.get('price', 0)
        discount = self.validated_data.get('discount', 0)
        discount_type = self.validated_data.get('discount_type', 'fixed')

        total = qty * price

        if discount_type == 'percentage':
            total -= total * (discount / 100)
        elif discount_type == 'fixed':
            total -= discount

        return round(total, 2)


# Purchase Serializer
class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    purchase_items = PurchaseItemSerializer(many=True, write_only=True)
    items = PurchaseItemSerializer(many=True, read_only=True)  # <- source removed

    class Meta:
        model = Purchase
        fields = [
            'id', 'supplier', 'supplier_name', 'total', 'date',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_charge_type',
            'overall_service_charge', 'overall_service_charge_type',
            'vat', 'vat_type', 'invoice_no', 'payment_status',
            'purchase_items', 'items'
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('purchase_items', [])
        purchase = Purchase.objects.create(**validated_data)

        total_amount = 0
        for item_data in items_data:
            product = item_data['product']
            qty = item_data['qty']
            price = item_data['price']

            purchase_item = PurchaseItem.objects.create(purchase=purchase, **item_data)

            # Update stock
            product.stock_qty += qty
            product.save(update_fields=['stock_qty'])

            total_amount += purchase_item.subtotal()

        # Apply overall purchase-level discounts/charges
        overall_discount = purchase.overall_discount
        if purchase.overall_discount_type == 'percentage':
            total_amount -= total_amount * (overall_discount / 100)
        else:
            total_amount -= overall_discount

        if purchase.overall_delivery_charge_type == 'percentage':
            total_amount += total_amount * (purchase.overall_delivery_charge / 100)
        else:
            total_amount += purchase.overall_delivery_charge

        if purchase.overall_service_charge_type == 'percentage':
            total_amount += total_amount * (purchase.overall_service_charge / 100)
        else:
            total_amount += purchase.overall_service_charge

        if purchase.vat_type == 'percentage':
            total_amount += total_amount * (purchase.vat / 100)
        else:
            total_amount += purchase.vat

        purchase.total = round(total_amount, 2)
        purchase.save(update_fields=['total'])

        return purchase
