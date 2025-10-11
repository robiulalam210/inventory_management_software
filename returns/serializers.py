# core/serializers.py
from rest_framework import serializers
from .models import SalesReturn, PurchaseReturn, BadStock

class SalesReturnSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesReturn
        fields = '__all__'


class PurchaseReturnSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseReturn
        fields = '__all__'


class BadStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = BadStock
        fields = '__all__'
