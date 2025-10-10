from rest_framework import serializers
from .models import Customer, Sale, SaleItem

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = SaleItem
        fields = ['id', 'sale', 'product', 'product_name', 'qty', 'price', 'subtotal']


class SaleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'customer', 'customer_name', 'total', 'date', 'items']
