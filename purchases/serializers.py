from rest_framework import serializers
from .models import Supplier, Purchase, PurchaseItem
from products.models import Product

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product', 'product_name', 'qty', 'price']


class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    items = PurchaseItemSerializer(many=True, required=False)

    class Meta:
        model = Purchase
        fields = ['id', 'supplier', 'supplier_name', 'total', 'date', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase = Purchase.objects.create(**validated_data)

        total = 0
        for item_data in items_data:
            product = item_data['product']
            qty = item_data['qty']
            price = item_data['price']

            # Create item
            PurchaseItem.objects.create(purchase=purchase, **item_data)

            # Auto increase product stock
            product.stock_qty += qty
            product.save()

            total += qty * price

        purchase.total = total
        purchase.save()
        return purchase
