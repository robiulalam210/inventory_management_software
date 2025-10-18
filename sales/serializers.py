from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from products.models import Product
from accounts.models import Account
from money_receipts.models import MoneyReceipt
from django.utils import timezone

# -----------------------------
# SaleItem Serializer - MUST BE DEFINED FIRST
# -----------------------------
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

# -----------------------------
# Sale Serializer - DEFINED AFTER SaleItemSerializer
# -----------------------------
class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source='customer'
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    items = SaleItemSerializer(many=True)
    due_amount = serializers.SerializerMethodField()
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    account_name = serializers.CharField(source='account.name', read_only=True, required=False, allow_null=True)
    
    # Make sale_by more flexible - accept integer or null
    vat = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    sale_by = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'sale_by', 'gross_total', 'net_total', 'payable_amount', 'paid_amount',
            'due_amount', 'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'customer_type', 'with_money_receipt', 'remark',
            'vat', 'service_charge', 'delivery_charge',
            'items'
        ]
        read_only_fields = [
            'invoice_no', 'gross_total', 'net_total', 'payable_amount', 'due_amount',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def validate_sale_by(self, value):
        """Validate sale_by field - allow null or valid account ID"""
        if value is None:
            return None
            
        try:
            account = Account.objects.get(id=value)
            return account
        except Account.DoesNotExist:
            # Instead of raising error, return None or get the first available account
            try:
                # Try to get any available account
                account = Account.objects.first()
                if account:
                    return account
                return None
            except:
                return None

    def create(self, validated_data):
        # Extract the write-only fields and map them to model fields
        vat_amount = validated_data.pop('vat', 0)
        service_charge_amount = validated_data.pop('service_charge', 0)
        delivery_charge_amount = validated_data.pop('delivery_charge', 0)
        items_data = validated_data.pop('items')
        sale_by = validated_data.pop('sale_by', None)
        
        # Map the write-only fields to actual model fields
        validated_data['overall_vat_amount'] = vat_amount
        validated_data['overall_service_charge'] = service_charge_amount
        validated_data['overall_delivery_charge'] = delivery_charge_amount
        
        # Handle sale_by - it's already validated in validate_sale_by method
        if sale_by:
            validated_data['sale_by'] = sale_by

        customer = validated_data.pop('customer')
        account = validated_data.get('account', None)
        paid_amount = validated_data.get('paid_amount', 0)

        request = self.context.get('request')
        company = getattr(request.user, 'company', None)
        validated_data['company'] = company

        if customer.company and company and customer.company != company:
            raise serializers.ValidationError(
                f"Cannot use customer from another company: {customer.name}"
            )

        # Create the sale with all mapped data
        sale = Sale.objects.create(customer=customer, **validated_data)

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

        # Update totals after creating all items
        sale.update_totals()
        
        # Handle payment and money receipt if paid amount > 0
        if account and paid_amount > 0:
            # Update account balance
            account.balance += paid_amount
            account.save(update_fields=['balance'])
            
            # Auto create MoneyReceipt
            MoneyReceipt.objects.create(
                company=company,
                customer=customer,
                sale=sale,
                amount=paid_amount,
                payment_method=validated_data.get('payment_method', ''),
                payment_date=timezone.now(),
                seller=request.user,
                account=account
            )

        return sale

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['gross_total'] = instance.gross_total
        representation['net_total'] = instance.net_total
        representation['payable_amount'] = instance.payable_amount
        representation['due_amount'] = instance.due_amount
        return representation


    pay_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        try:
            sale = Sale.objects.get(id=attrs['sale_id'])
        except Sale.DoesNotExist:
            raise serializers.ValidationError("Sale not found.")

        if attrs['pay_amount'] <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0.")

        if attrs['pay_amount'] > sale.payable_amount - sale.paid_amount:
            raise serializers.ValidationError(
                f"Payment exceeds due amount ({sale.payable_amount - sale.paid_amount})."
            )

        attrs['sale'] = sale
        return attrs

    def save(self, **kwargs):
        sale = self.validated_data['sale']
        pay_amount = self.validated_data['pay_amount']
        sale.paid_amount += pay_amount
        sale.due_amount = max(0, sale.payable_amount - sale.paid_amount)
        sale.save(update_fields=['paid_amount', 'due_amount'])
        return sale