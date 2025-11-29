from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from products.models import Product
from accounts.models import Account
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()


class SaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_id', 'product_name', 'quantity', 'unit_price',
            'discount', 'discount_type', 'subtotal'
        ]
        read_only_fields = ['id', 'product_name', 'subtotal']

    def get_subtotal(self, obj):
        return obj.subtotal()


class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account',
        required=False,
        allow_null=True
    )
    account_name = serializers.CharField(source='account.name', read_only=True)
    sale_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    sale_by_name = serializers.CharField(source='sale_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    items = SaleItemSerializer(many=True, write_only=True)
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    due_amount = serializers.SerializerMethodField()
    payment_status = serializers.CharField(read_only=True)
    invoice_no = serializers.CharField(read_only=True)
    sale_date = serializers.DateTimeField(read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'sale_by', 'sale_by_name', 'created_by_name',
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'paid_amount', 'due_amount', 'change_amount',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'customer_type', 'with_money_receipt', 'remark',
            'items', 'payment_status'
        ]
        read_only_fields = [
            'id', 'invoice_no', 'gross_total', 'net_total', 'grand_total',
            'payable_amount', 'due_amount', 'change_amount',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount',
            'created_by_name', 'sale_by_name'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def validate(self, attrs):
        customer_type = attrs.get('customer_type', 'walk_in')
        paid_amount = attrs.get('paid_amount', 0)
        items = attrs.get('items', [])

        if not items:
            raise serializers.ValidationError({'items': 'At least one item is required.'})

        if customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({'customer': 'Saved customer must have a record.'})

        if customer_type == 'walk_in' and paid_amount and paid_amount < 0:
            raise serializers.ValidationError({'paid_amount': 'Paid amount must be positive.'})

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale_by_data = validated_data.pop('sale_by', None)

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            validated_data['sale_by'] = sale_by_data if sale_by_data else request.user
            if hasattr(request.user, 'company'):
                validated_data['company'] = request.user.company

        if validated_data.get('customer_type') == 'walk_in':
            validated_data['customer'] = None
            validated_data.setdefault('customer_name', "Walk-in Customer")

        # Set sale charges defaults if missing
        for field in ['vat', 'service_charge', 'delivery_charge']:
            validated_data[f'overall_{field if field != "vat" else "vat_amount"}'] = validated_data.pop(field, 0)

        with transaction.atomic():
            sale = Sale.objects.create(**validated_data)

            # Create sale items
            sale_items = [
                SaleItem(
                    sale=sale,
                    product=i['product'],
                    quantity=i['quantity'],
                    unit_price=i['unit_price'],
                    discount=i.get('discount', 0),
                    discount_type=i.get('discount_type', 'fixed')
                ) for i in items_data
            ]
            SaleItem.objects.bulk_create(sale_items)
            sale.update_totals()

            # Handle account payment
            account = validated_data.get('account')
            if account and sale.paid_amount > 0:
                account.balance += sale.paid_amount
                account.save(update_fields=['balance'])

                if validated_data.get('with_money_receipt') == 'Yes':
                    sale.create_money_receipt()

            return sale

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['items'] = SaleItemSerializer(instance.items.all(), many=True).data
        rep['customer_name'] = instance.customer.name if instance.customer else "Walk-in Customer"
        return rep
