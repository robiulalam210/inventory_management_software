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
    
    # ✅ FIXED: Make paid_amount writable
    paid_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, 
        default=0
    )

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
            'created_by_name', 'sale_by_name', 'payment_status'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def validate(self, attrs):
        customer_type = attrs.get('customer_type', 'walk_in')
        paid_amount = attrs.get('paid_amount', 0)
        items = attrs.get('items', [])
        payment_method = attrs.get('payment_method')
        account = attrs.get('account')

        if not items:
            raise serializers.ValidationError({'items': 'At least one item is required.'})

        if customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({'customer': 'Saved customer must have a record.'})

        # ✅ FIXED: Validate payment details when payment is made
        if paid_amount and paid_amount > 0:
            if not payment_method:
                raise serializers.ValidationError({
                    'payment_method': 'Payment method is required when making a payment.'
                })
            if not account:
                raise serializers.ValidationError({
                    'account': 'Account is required when making a payment.'
                })

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale_by_data = validated_data.pop('sale_by', None)
        
        # ✅ FIXED: Extract paid_amount before creating sale
        paid_amount = validated_data.get('paid_amount', 0)

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            validated_data['sale_by'] = sale_by_data if sale_by_data else request.user
            if hasattr(request.user, 'company'):
                validated_data['company'] = request.user.company

        if validated_data.get('customer_type') == 'walk_in':
            validated_data['customer'] = None
            validated_data.setdefault('customer_name', "Walk-in Customer")

        # ✅ FIXED: Handle charge fields properly
        charge_fields_mapping = {
            'vat': 'overall_vat_amount',
            'service_charge': 'overall_service_charge', 
            'delivery_charge': 'overall_delivery_charge'
        }
        
        for source_field, target_field in charge_fields_mapping.items():
            if source_field in validated_data:
                validated_data[target_field] = validated_data.pop(source_field)

        with transaction.atomic():
            # ✅ FIXED: Create sale with paid_amount
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
            
            # ✅ FIXED: Update totals to calculate correct amounts
            sale.update_totals()
            
            # ✅ FIXED: Handle payment and money receipt
            account = validated_data.get('account')
            if account and paid_amount > 0:
                # Update account balance
                account.balance += paid_amount
                account.save(update_fields=['balance'])
                
                logger.info(f"💰 Account {account.name} balance updated: +{paid_amount}")

                # Create money receipt if requested
                if validated_data.get('with_money_receipt') == 'Yes':
                    money_receipt = sale.create_money_receipt()
                    if money_receipt:
                        logger.info(f"🧾 Money receipt created: {money_receipt.mr_no}")
                else:
                    # Create direct transaction
                    transaction_obj = sale.create_transaction()
                    if transaction_obj:
                        logger.info(f"💳 Direct transaction created: {transaction_obj.transaction_no}")

            # ✅ FIXED: Refresh sale to get updated totals
            sale.refresh_from_db()
            
            return sale

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['items'] = SaleItemSerializer(instance.items.all(), many=True).data
        rep['customer_name'] = instance.customer.name if instance.customer else "Walk-in Customer"
        
        # ✅ FIXED: Ensure correct payment amounts are shown
        rep['paid_amount'] = float(instance.paid_amount)
        rep['due_amount'] = float(instance.due_amount)
        rep['change_amount'] = float(instance.change_amount)
        rep['grand_total'] = float(instance.grand_total)
        
        return rep