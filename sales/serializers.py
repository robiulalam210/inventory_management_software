from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from products.models import Product
from accounts.models import Account
from money_receipts.models import MoneyReceipt
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

class SaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product'
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price',
                  'discount', 'discount_type', 'subtotal']

    def get_subtotal(self, obj):
        return obj.subtotal()

    def validate(self, attrs):
        product = attrs['product']
        qty = attrs['quantity']
        request = self.context.get('request')

        if qty > product.stock_qty:
            raise serializers.ValidationError(
                f"Not enough stock for {product.name}. Available: {product.stock_qty}"
            )

        if request and hasattr(request.user, 'company') and product.company != request.user.company:
            raise serializers.ValidationError(
                f"Cannot use product from another company: {product.company.name}"
            )

        return attrs

    def create(self, validated_data):
        product = validated_data['product']
        qty = validated_data['quantity']
        product.stock_qty -= qty
        product.save(update_fields=['stock_qty'])
        return SaleItem.objects.create(**validated_data)

class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), 
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(required=False, allow_blank=True)
    items = SaleItemSerializer(many=True)
    due_amount = serializers.SerializerMethodField()
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), 
        source='account', 
        allow_null=True, 
        required=False
    )
    account_name = serializers.CharField(source='account.name', read_only=True, required=False, allow_null=True)
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    sale_by_name = serializers.CharField(source='sale_by.username', read_only=True)
    
    vat = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    
    paid_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, 
        default=0,
        min_value=0
    )
    
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'sale_by_name', 'created_by_name',
            'gross_total', 'net_total', 'grand_total', 'payable_amount', 'paid_amount',
            'due_amount', 'change_amount', 'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'customer_type', 'with_money_receipt', 'remark',
            'vat', 'service_charge', 'delivery_charge',
            'items'
        ]
        read_only_fields = [
            'invoice_no', 'gross_total', 'net_total', 'grand_total', 
            'payable_amount', 'due_amount', 'change_amount',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount',
            'created_by_name', 'sale_by_name'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def get_walk_in_customer(self, company, customer_name=None):
        name = customer_name or 'Walk-in Customer'
        
        try:
            customer = Customer.objects.get(
                name=name,
                company=company
            )
            return customer
        except Customer.DoesNotExist:
            return None

    def validate(self, attrs):
        customer_type = attrs.get('customer_type', 'walk_in')
        with_money_receipt = attrs.get('with_money_receipt', 'No')
        paid_amount = attrs.get('paid_amount', 0)
        
        # ✅ FIXED: Remove customer requirement for walk-in with money receipt
        if customer_type == 'walk_in' and with_money_receipt == 'Yes':
            if not paid_amount or paid_amount <= 0:
                raise serializers.ValidationError({
                    'paid_amount': 'Walk-in customers with money receipt must provide payment amount.'
                })
            # REMOVED: Customer requirement since model allows null
        
        # Saved customers always need customer record
        if customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({
                'customer': 'Saved customers must have a customer record.'
            })
        
        return attrs

    def create(self, validated_data):
        try:
            items_data = validated_data.pop('items')
            vat_amount = validated_data.pop('vat', 0)
            service_charge_amount = validated_data.pop('service_charge', 0)
            delivery_charge_amount = validated_data.pop('delivery_charge', 0)
            original_paid_amount = validated_data.get('paid_amount', 0)
            with_money_receipt = validated_data.get('with_money_receipt', 'No')
            customer_type = validated_data.get('customer_type', 'walk_in')
            
            validated_data['overall_vat_amount'] = vat_amount
            validated_data['overall_service_charge'] = service_charge_amount
            validated_data['overall_delivery_charge'] = delivery_charge_amount
            
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['created_by'] = request.user
                validated_data['sale_by'] = request.user
                validated_data['company'] = getattr(request.user, 'company', None)

            # ✅ FIXED: No customer creation - use existing customer or None
            customer = validated_data.get('customer')
            if not customer and customer_type == 'walk_in':
                customer = self.get_walk_in_customer(
                    validated_data['company'],
                    validated_data.get('customer_name')
                )
                # If no customer found, keep it as None
                validated_data['customer'] = customer

            # Validate payment requirements ONLY (no customer requirement)
            if customer_type == 'walk_in' and with_money_receipt == 'Yes':
                if original_paid_amount <= 0:
                    raise serializers.ValidationError(
                        "Walk-in customers with money receipt must pay the full amount immediately."
                    )
                # ✅ REMOVED: Customer requirement check

            with transaction.atomic():
                validated_data['paid_amount'] = 0
                sale = Sale.objects.create(**validated_data)

                # Create SaleItems
                for item in items_data:
                    SaleItem.objects.create(
                        sale=sale,
                        product=item['product'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price'],
                        discount=item.get('discount', 0),
                        discount_type=item.get('discount_type', 'fixed')
                    )

                sale.update_totals()
                
                if original_paid_amount > 0:
                    if customer_type == 'walk_in' and original_paid_amount < sale.payable_amount:
                        raise serializers.ValidationError(
                            f"Walk-in customers must pay at least the full amount. "
                            f"Payable: {sale.payable_amount}, Paid: {original_paid_amount}"
                        )
                    
                    sale.paid_amount = original_paid_amount
                    sale.save(update_fields=['paid_amount'])
                    sale.update_totals()

                # Handle account balance and money receipt
                account = validated_data.get('account')
                if account and sale.paid_amount > 0:
                    account.balance += sale.paid_amount
                    account.save(update_fields=['balance'])
                    
                    if with_money_receipt == 'Yes' and sale.paid_amount > 0:
                        try:
                            # Money receipt will work even with null customer
                            sale.create_money_receipt()
                        except Exception as e:
                            print(f"Error creating money receipt: {e}")

                return sale

        except serializers.ValidationError:
            raise
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating sale: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise serializers.ValidationError(f"Failed to create sale: {str(e)}")
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['gross_total'] = instance.gross_total
        representation['net_total'] = instance.net_total
        representation['grand_total'] = instance.grand_total
        representation['payable_amount'] = instance.payable_amount
        representation['due_amount'] = instance.due_amount
        representation['change_amount'] = instance.change_amount
        
        if instance.customer:
            representation['customer_name'] = instance.customer.name
        else:
            representation['customer_name'] = 'Walk-in Customer'
            
        return representation

class DueSaleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    invoice_no = serializers.CharField(read_only=True)
    sale_date = serializers.DateTimeField(read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    due_amount = serializers.SerializerMethodField()
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_name', 'sale_date', 
            'grand_total', 'paid_amount', 'due_amount', 'payment_status'
        ]
    
    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)