# returns/serializers.py
from rest_framework import serializers
from .models import SalesReturn, PurchaseReturn, BadStock, SalesReturnItem, PurchaseReturnItem
from accounts.models import Account, Company
from products.models import Product

class SalesReturnItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    product_name = serializers.CharField(read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesReturnItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'damage_quantity', 
                 'unit_price', 'discount', 'discount_type', 'total']
        read_only_fields = ['sales_return']


class SalesReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    # Remove warehouse_id field
    items = SalesReturnItemSerializer(many=True)
    return_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesReturn
        fields = ['id', 'receipt_no', 'customer_name', 'return_date', 
                 'account_id', 'payment_method', 'reason', 'return_charge', 
                 'return_charge_type', 'return_amount', 'status', 'company_id', 'items']
        read_only_fields = ['receipt_no', 'return_amount', 'status']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sales_return = SalesReturn.objects.create(**validated_data)
        
        total_amount = 0
        for item_data in items_data:
            item = SalesReturnItem.objects.create(sales_return=sales_return, **item_data)
            total_amount += item.total
            
        # Calculate final return amount with return charge
        if sales_return.return_charge_type == 'percentage' and sales_return.return_charge > 0:
            return_charge_amount = (total_amount * sales_return.return_charge) / 100
        else:
            return_charge_amount = sales_return.return_charge
            
        sales_return.return_amount = total_amount + return_charge_amount
        sales_return.save()
        
        return sales_return


class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    product_name = serializers.CharField(read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseReturnItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price', 
                 'discount', 'discount_type', 'total']
        read_only_fields = ['purchase_return']


class PurchaseReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    # Remove warehouse_id field
    items = PurchaseReturnItemSerializer(many=True)
    return_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseReturn
        fields = ['id', 'supplier', 'invoice_no', 'return_date', 
                 'account_id', 'payment_method', 'return_charge', 'return_charge_type', 
                 'return_amount', 'reason', 'status', 'company_id', 'items']
        read_only_fields = ['return_amount', 'status']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase_return = PurchaseReturn.objects.create(**validated_data)
        
        total_amount = 0
        for item_data in items_data:
            item = PurchaseReturnItem.objects.create(purchase_return=purchase_return, **item_data)
            total_amount += item.total
            
        # Calculate final return amount with return charge
        if purchase_return.return_charge_type == 'percentage' and purchase_return.return_charge > 0:
            return_charge_amount = (total_amount * purchase_return.return_charge) / 100
        else:
            return_charge_amount = purchase_return.return_charge
            
        purchase_return.return_amount = total_amount + return_charge_amount
        purchase_return.save()
        
        return purchase_return


class BadStockSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = BadStock
        fields = ['id', 'product', 'product_name', 'quantity', 'company_id', 
                 'reason', 'date', 'reference_type', 'reference_id']