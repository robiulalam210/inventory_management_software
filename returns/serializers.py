from rest_framework import serializers
from .models import SalesReturn, PurchaseReturn, BadStock,Account, Company, SalesReturnItem
from .models import PurchaseReturn, PurchaseReturnItem
from accounts.models import Account, Company

class SalesReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesReturnItem
        fields = '__all__'
        read_only_fields = ['sales_return']


class SalesReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    items = SalesReturnItemSerializer(many=True)

    class Meta:
        model = SalesReturn
        fields = '__all__'

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sales_return = SalesReturn.objects.create(**validated_data)
        for item_data in items_data:
            SalesReturnItem.objects.create(sales_return=sales_return, **item_data)
        return sales_return

class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseReturnItem
        fields = '__all__'
        read_only_fields = ['purchase_return']


class PurchaseReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    items = PurchaseReturnItemSerializer(many=True)

    class Meta:
        model = PurchaseReturn
        fields = '__all__'

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase_return = PurchaseReturn.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseReturnItem.objects.create(purchase_return=purchase_return, **item_data)
        return purchase_return

class BadStockSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )

    class Meta:
        model = BadStock
        fields = '__all__'