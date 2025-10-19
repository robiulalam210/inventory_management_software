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
        queryset=Customer.objects.all(), 
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(required=False, allow_blank=True)
    items = SaleItemSerializer(many=True)
    due_amount = serializers.SerializerMethodField()
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), 
        source='account', 
        allow_null=True, 
        required=False
    )
    account_name = serializers.CharField(source='account.name', read_only=True, required=False, allow_null=True)
    
    # Write-only fields for charges
    vat = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    
    # Make sale_by more flexible
    sale_by = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Add paid_amount field for payment - MAKE IT REQUIRED FOR MONEY RECEIPT
    paid_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, 
        default=0,
        min_value=0
    )
    
    # Add grand_total field in read-only
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'sale_type',
            'sale_date', 'sale_by', 'gross_total', 'net_total', 'grand_total', 'payable_amount', 'paid_amount',
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
            'invoice_no', 'gross_total', 'net_total', 'grand_total', 'payable_amount', 'due_amount',
            'overall_delivery_charge', 'overall_service_charge', 'overall_vat_amount'
        ]

    def get_due_amount(self, obj):
        return max(0, obj.payable_amount - obj.paid_amount)

    def get_or_create_walk_in_customer(self, company, customer_name=None):
        """Get or create walk-in customer"""
        name = customer_name or 'Walk-in Customer'
        
        try:
            customer = Customer.objects.get(
                name=name,
                company=company
            )
            return customer
        except Customer.DoesNotExist:
            customer = Customer.objects.create(
                name=name,
                company=company,
                phone='0000000000',
                address='Walk-in customer'
            )
            return customer

    def validate_sale_by(self, value):
        """Validate sale_by field - allow null or valid account ID"""
        if value is None:
            return None
            
        try:
            account = Account.objects.get(id=value)
            return account
        except Account.DoesNotExist:
            try:
                account = Account.objects.first()
                if account:
                    return account
                return None
            except:
                return None

    def validate(self, attrs):
        """Overall validation with payment handling"""
        customer_type = attrs.get('customer_type', 'walk_in')
        paid_amount = attrs.get('paid_amount', 0)
        with_money_receipt = attrs.get('with_money_receipt', 'No')
        account = attrs.get('account')
        
        # If with_money_receipt is 'Yes', ensure paid_amount > 0 and account is provided
        if with_money_receipt == 'Yes':
            if paid_amount <= 0:
                raise serializers.ValidationError({
                    "paid_amount": "Payment amount must be greater than 0 when money receipt is required."
                })
            if not account:
                raise serializers.ValidationError({
                    "account_id": "Account is required when money receipt is generated."
                })
        
        # For walk-in customers, paid_amount should equal payable_amount
        if customer_type == 'walk_in' and paid_amount > 0:
            # We'll handle this in create method after totals are calculated
            pass
        
        request = self.context.get('request')
        company = getattr(request.user, 'company', None) if request else None

        # Handle walk-in customer
        if customer_type == 'walk_in':
            customer = attrs.get('customer')
            customer_name = attrs.get('customer_name')
            
            if not customer:
                walk_in_customer = self.get_or_create_walk_in_customer(company, customer_name)
                attrs['customer'] = walk_in_customer
            
            if 'customer_name' in attrs:
                attrs.pop('customer_name')
        
        # For saved customers, customer_id is required
        elif customer_type == 'saved_customer' and not attrs.get('customer'):
            raise serializers.ValidationError({
                "customer_id": "This field is required for saved customers."
            })
        
        # Check if customer belongs to same company
        if request and hasattr(request.user, 'company') and attrs.get('customer') and attrs['customer'].company:
            if attrs['customer'].company != request.user.company:
                raise serializers.ValidationError({
                    "customer_id": f"Cannot use customer from another company: {attrs['customer'].company.name}"
                })
        
        return attrs

    def create(self, validated_data):
        try:
            # Extract write-only fields
            vat_amount = validated_data.pop('vat', 0)
            service_charge_amount = validated_data.pop('service_charge', 0)
            delivery_charge_amount = validated_data.pop('delivery_charge', 0)
            items_data = validated_data.pop('items')
            sale_by = validated_data.pop('sale_by', None)
            paid_amount = validated_data.get('paid_amount', 0)
            with_money_receipt = validated_data.get('with_money_receipt', 'No')
            
            # Map write-only fields to actual model fields
            validated_data['overall_vat_amount'] = vat_amount
            validated_data['overall_service_charge'] = service_charge_amount
            validated_data['overall_delivery_charge'] = delivery_charge_amount
            
            # Handle sale_by
            if sale_by:
                validated_data['sale_by'] = sale_by

            customer = validated_data.get('customer')
            account = validated_data.get('account', None)

            request = self.context.get('request')
            company = getattr(request.user, 'company', None)
            validated_data['company'] = company

            # Ensure customer is set
            if not customer:
                customer = self.get_or_create_walk_in_customer(company)
                validated_data['customer'] = customer

            # Create the sale
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

            # Update totals after creating all items
            sale.update_totals()
            
            # Handle walk-in customers - auto set paid_amount to payable_amount
            if sale.customer_type == 'walk_in':
                sale.paid_amount = sale.payable_amount
                sale.due_amount = 0
                sale.payment_status = 'paid'
                sale.save(update_fields=['paid_amount', 'due_amount', 'payment_status'])
                paid_amount = sale.payable_amount  # Update paid_amount for receipt creation
            
            # Handle payment and money receipt creation
            if account and paid_amount > 0:
                # Update account balance
                account.balance += paid_amount
                account.save(update_fields=['balance'])
                
                # Auto create MoneyReceipt if with_money_receipt is 'Yes'
                if with_money_receipt == 'Yes':
                    try:
                        money_receipt = MoneyReceipt.objects.create(
                            company=company,
                            customer=customer,
                            sale=sale,
                            amount=paid_amount,
                            payment_method=validated_data.get('payment_method', 'Cash'),
                            payment_date=timezone.now(),
                            seller=request.user,
                            account=account,
                            remark=f"Payment received for sale {sale.invoice_no}"
                        )
                        print(f"Money receipt created: {money_receipt.mr_no}")
                    except Exception as e:
                        print(f"Error creating money receipt: {e}")
                        # Don't raise error, just log it

            return sale

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating sale: {str(e)}")
            raise serializers.ValidationError(f"Failed to create sale: {str(e)}")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['gross_total'] = instance.gross_total
        representation['net_total'] = instance.net_total
        representation['grand_total'] = instance.grand_total
        representation['payable_amount'] = instance.payable_amount
        representation['due_amount'] = instance.due_amount
        
        # Add customer_name to response
        if instance.customer:
            representation['customer_name'] = instance.customer.name
        else:
            representation['customer_name'] = 'Walk-in Customer'
            
        return representation
    
# sales/serializers.py
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