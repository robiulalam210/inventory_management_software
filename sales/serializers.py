from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from products.models import Product

# Customer Serializer
class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

# SaleItem Serializer
class SaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(source='product', queryset=Product.objects.all())
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price', 'discount', 'discount_type', 'subtotal']

    def get_subtotal(self, obj):
        return obj.subtotal()

# Sale Serializer
class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(source='customer', queryset=Customer.objects.all())
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    items = SaleItemSerializer(many=True)
    due_amount = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'gross_total', 'net_total', 'payable_amount', 'paid_amount', 'due_amount',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'items'
        ]

    def get_due_amount(self, obj):
        return round(obj.payable_amount - obj.paid_amount, 2)

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        sale.update_totals()
        return sale

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                SaleItem.objects.create(sale=instance, **item_data)

        instance.update_totals()
        return instance

# Due Payment Serializer (FIXED)
class DuePaymentSerializer(serializers.Serializer):
    sale_id = serializers.IntegerField()
    pay_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        sale_id = attrs.get('sale_id')
        pay_amount = attrs.get('pay_amount')

        try:
            sale = Sale.objects.get(id=sale_id)
        except Sale.DoesNotExist:
            raise serializers.ValidationError("Sale not found.")

        if pay_amount <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0.")

        # Recalculate due amount
        due_amount = sale.payable_amount - sale.paid_amount
        if pay_amount > due_amount:
            raise serializers.ValidationError(f"Payment exceeds due amount ({due_amount}).")

        attrs['sale'] = sale
        return attrs

    def save(self, **kwargs):
        sale = self.validated_data['sale']
        pay_amount = self.validated_data['pay_amount']

        sale.paid_amount += pay_amount
        sale.due_amount = max(0, sale.payable_amount - sale.paid_amount)
        sale.save(update_fields=['paid_amount', 'due_amount'])
        return sale
