from rest_framework import serializers
from .models import SalesReturn, PurchaseReturn, BadStock,Account, Company

class SalesReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )

    class Meta:
        model = SalesReturn
        fields = '__all__'

class PurchaseReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )

    class Meta:
        model = PurchaseReturn
        fields = '__all__'

class BadStockSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )

    class Meta:
        model = BadStock
        fields = '__all__'