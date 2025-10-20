import logging
import traceback
from rest_framework import serializers
from .models import Purchase, PurchaseItem
from products.models import Product
from accounts.models import Account
from django.db import transaction
from decimal import Decimal

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='subtotal')

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product_id', 'product_name', 'qty', 'price', 'discount', 'discount_type', 'product_total']
        read_only_fields = ['id', 'product_name', 'product_total']

class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    purchase_items = PurchaseItemSerializer(many=True, write_only=True, required=False)
    items = PurchaseItemSerializer(many=True, read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False, write_only=True
    )
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    payment_method = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    # Payment fields
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Purchase date
    purchase_date = serializers.DateField(required=True)
    
    # Instant pay field
    instant_pay = serializers.BooleanField(write_only=True, default=False)
    
    # Additional fields from request
    delivery_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    service_charge = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False, default=0)
    sub_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='total')
    
    # Charge type fields
    overall_service_type = serializers.CharField(write_only=True, required=False, default='fixed')
    overall_delivery_type = serializers.CharField(write_only=True, required=False, default='fixed')

    class Meta:
        model = Purchase
        fields = [
            'id', 'company', 'supplier', 'supplier_name', 'purchase_date', 'total', 'grand_total',
            'paid_amount', 'due_amount', 'change_amount', 'instant_pay',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_charge_type',
            'overall_service_charge', 'overall_service_charge_type',
            'vat', 'vat_type', 'invoice_no', 'payment_status', 'return_amount',
            'account_id', 'account_name', 'payment_method', 'remark',
            'purchase_items', 'items', 'delivery_charge', 'service_charge',
            'sub_total', 'overall_service_type', 'overall_delivery_type'
        ]
        read_only_fields = [
            'id', 'company', 'total', 'grand_total', 'invoice_no', 'payment_status',
            'due_amount', 'change_amount', 'supplier_name', 'account_name', 'sub_total'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        
        # Validate purchase items for creation
        if request and getattr(request, "method", None) == 'POST':
            purchase_items = attrs.get('purchase_items') or []
            if not purchase_items:
                raise serializers.ValidationError({"purchase_items": "At least one purchase item is required."})
            
            # Validate that all products belong to user's company
            user_company = request.user.company
            for item_data in purchase_items:
                product = item_data.get('product')
                if product and hasattr(product, 'company') and product.company != user_company:
                    raise serializers.ValidationError({
                        "purchase_items": f"Product '{product.name}' does not belong to your company."
                    })
        
        # Validate instant payment requirements
        instant_pay = attrs.get('instant_pay', False)
        if instant_pay:
            if not attrs.get('payment_method'):
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required for instant payment."
                })
            if not attrs.get('account'):
                raise serializers.ValidationError({
                    "account": "Account is required for instant payment."
                })
        
        return attrs

    def create(self, validated_data):
        logger = logging.getLogger(__name__)
        try:
            request = self.context.get('request')
            if not request or not hasattr(request.user, 'company') or not request.user.company:
                raise serializers.ValidationError("User does not belong to a company.")

            items_data = validated_data.pop('purchase_items', [])
            instant_pay = validated_data.pop('instant_pay', False)
            delivery_charge = validated_data.pop('delivery_charge', 0)
            service_charge = validated_data.pop('service_charge', 0)
            overall_service_type = validated_data.pop('overall_service_type', 'fixed')
            overall_delivery_type = validated_data.pop('overall_delivery_type', 'fixed')
            
            # Map write-only fields to model fields
            validated_data['overall_delivery_charge'] = delivery_charge
            validated_data['overall_service_charge'] = service_charge
            validated_data['overall_delivery_charge_type'] = overall_delivery_type
            validated_data['overall_service_charge_type'] = overall_service_type
            
            account = validated_data.get('account', None)
            payment_method = validated_data.get('payment_method', None)
            
            validated_data['company'] = request.user.company
            validated_data['created_by'] = request.user

            with transaction.atomic():
                # Create purchase first (without items)
                purchase = Purchase.objects.create(**validated_data)
                print(f"✅ Created purchase ID: {purchase.id} for supplier ID: {purchase.supplier_id}")

                # Create purchase items - let PurchaseItem.save() handle stock updates
                for item_data in items_data:
                    PurchaseItem.objects.create(purchase=purchase, **item_data)

                # Calculate totals - this will trigger supplier update
                purchase.update_totals()

                # Handle instant payment
                if instant_pay and account and payment_method:
                    purchase.instant_pay(payment_method, account)

                # Debug: Check supplier after creation
                print(f"🔄 Purchase created. Checking supplier totals...")
                if purchase.supplier:
                    purchase.supplier.refresh_from_db()
                    print(f"📊 Supplier '{purchase.supplier.name}' (ID: {purchase.supplier.id}) - "
                          f"Purchases: {purchase.supplier.total_purchases}, Due: {purchase.supplier.total_due}")

            return purchase
        except Exception as e:
            logger.exception("Exception in PurchaseSerializer.create")
            raise serializers.ValidationError({
                "error": f"Failed to create purchase: {str(e)}"
            })

    def update(self, instance, validated_data):
        items_data = validated_data.pop('purchase_items', None)
        instant_pay = validated_data.pop('instant_pay', False)
        account = validated_data.get('account', instance.account)
        payment_method = validated_data.get('payment_method', instance.payment_method)
        
        with transaction.atomic():
            # Update purchase fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            # Update items if provided
            if items_data is not None:
                # Delete existing items
                instance.items.all().delete()
                
                # Create new items
                for item_data in items_data:
                    PurchaseItem.objects.create(purchase=instance, **item_data)
            
            instance.update_totals()
            
            # Handle instant payment
            if instant_pay and account and payment_method:
                instance.instant_pay(payment_method, account)
            
            return instance