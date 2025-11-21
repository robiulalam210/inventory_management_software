# purchases/serializers.py
import logging
import traceback
from rest_framework import serializers
from .models import Purchase, PurchaseItem
from products.models import Product
from accounts.models import Account
from django.db import transaction as db_transaction
from decimal import Decimal

logger = logging.getLogger(__name__)

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

    def validate_price(self, value):
        """Ensure price is valid"""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value

    def validate_qty(self, value):
        """Ensure quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, attrs):
        """Validate item data"""
        price = attrs.get('price', 0)
        qty = attrs.get('qty', 0)
        discount = attrs.get('discount', 0)
        discount_type = attrs.get('discount_type', 'fixed')
        
        # Calculate subtotal to ensure it's valid
        subtotal = price * qty
        if discount_type == 'percentage':
            discount_amount = subtotal * (discount / Decimal('100.00'))
        else:
            discount_amount = discount
            
        final_total = max(Decimal('0.00'), subtotal - discount_amount)
        
        if final_total <= 0:
            raise serializers.ValidationError("Item total must be greater than 0 after discount")
            
        return attrs

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
    delivery_charge = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False, default=0,
        source='overall_delivery_charge'
    )
    service_charge = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False, default=0,
        source='overall_service_charge'
    )
    sub_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='total')
    
    # Charge type fields
    overall_service_type = serializers.CharField(
        write_only=True, required=False, default='fixed', 
        source='overall_service_charge_type'
    )
    overall_delivery_type = serializers.CharField(
        write_only=True, required=False, default='fixed', 
        source='overall_delivery_charge_type'
    )

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
            
            # Validate that all products have valid prices
            for i, item_data in enumerate(purchase_items):
                product = item_data.get('product')
                price = item_data.get('price', 0)
                qty = item_data.get('qty', 0)
                
                if not product:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Product is required."
                    })
                
                if price <= 0:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Price must be greater than 0 for product '{product.name}'."
                    })
                
                if qty <= 0:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Quantity must be greater than 0 for product '{product.name}'."
                    })
                
                # Validate that products belong to user's company
                user_company = request.user.company
                if product and hasattr(product, 'company') and product.company != user_company:
                    raise serializers.ValidationError({
                        "purchase_items": f"Item {i+1}: Product '{product.name}' does not belong to your company."
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
        
        # Validate discount doesn't create negative totals
        overall_discount = attrs.get('overall_discount', 0)
        if overall_discount < 0:
            raise serializers.ValidationError({
                "overall_discount": "Discount cannot be negative."
            })
        
        # Validate charges
        delivery_charge = attrs.get('overall_delivery_charge', 0)
        service_charge = attrs.get('overall_service_charge', 0)
        vat = attrs.get('vat', 0)
        
        if delivery_charge < 0:
            raise serializers.ValidationError({"delivery_charge": "Delivery charge cannot be negative."})
        if service_charge < 0:
            raise serializers.ValidationError({"service_charge": "Service charge cannot be negative."})
        if vat < 0:
            raise serializers.ValidationError({"vat": "VAT cannot be negative."})
        
        return attrs

    def create(self, validated_data):
        try:
            request = self.context.get('request')
            if not request or not hasattr(request.user, 'company') or not request.user.company:
                raise serializers.ValidationError("User does not belong to a company.")

            items_data = validated_data.pop('purchase_items', [])
            instant_pay = validated_data.pop('instant_pay', False)
            
            account = validated_data.get('account', None)
            payment_method = validated_data.get('payment_method', None)
            paid_amount = validated_data.get('paid_amount', Decimal('0.00'))
            
            validated_data['company'] = request.user.company
            validated_data['created_by'] = request.user

            with db_transaction.atomic():
                # Create purchase first (without items)
                purchase = Purchase.objects.create(**validated_data)
                logger.info(f"✅ Created purchase ID: {purchase.id} for supplier ID: {purchase.supplier_id}")

                # Create purchase items
                created_items = []
                for item_data in items_data:
                    item = PurchaseItem.objects.create(purchase=purchase, **item_data)
                    created_items.append(item)
                    logger.info(f"📦 Created item: {item.product.name} x {item.qty} @ {item.price}")

                # Update totals to calculate the actual totals
                logger.info(f"🔄 Calling update_totals for purchase {purchase.id}")
                purchase.update_totals(force_update=True)
                
                # Refresh from database to get updated values
                purchase.refresh_from_db()
                logger.info(f"📊 Final purchase totals - Total: {purchase.total}, Grand Total: {purchase.grand_total}, Paid: {purchase.paid_amount}")

                # ✅ FIXED: Handle payments properly
                if instant_pay and account and payment_method:
                    if paid_amount > 0:
                        # Create transaction directly without calling instant_pay
                        logger.info(f"💰 Creating instant payment transaction: {paid_amount}")
                        from transactions.models import Transaction
                        transaction_obj = Transaction.create_for_purchase_payment(
                            purchase=purchase,
                            amount=paid_amount,
                            payment_method=payment_method,
                            account=account,
                            created_by=request.user
                        )
                        if transaction_obj:
                            logger.info(f"✅ Instant payment transaction created: {transaction_obj.transaction_no}")
                    elif purchase.due_amount > 0:
                        # Use the original instant_pay method without paid_amount
                        logger.info(f"💰 Processing instant payment for due_amount: {purchase.due_amount}")
                        purchase.instant_pay(payment_method, account)
                elif paid_amount > 0 and account and payment_method:
                    # If not instant_pay but paid_amount provided, create single transaction
                    logger.info(f"💰 Creating payment transaction: {paid_amount}")
                    from transactions.models import Transaction
                    transaction_obj = Transaction.create_for_purchase_payment(
                        purchase=purchase,
                        amount=paid_amount,
                        payment_method=payment_method,
                        account=account,
                        created_by=request.user
                    )
                    if transaction_obj:
                        logger.info(f"✅ Payment transaction created: {transaction_obj.transaction_no}")

                # Update supplier totals
                if purchase.supplier:
                    logger.info(f"🔄 Updating supplier totals for {purchase.supplier.name}")
                    purchase.supplier.update_purchase_totals()

            logger.info(f"🎉 Purchase creation completed successfully. ID: {purchase.id}, Invoice: {purchase.invoice_no}")
            return purchase
            
        except Exception as e:
            logger.exception("❌ Exception in PurchaseSerializer.create")
            raise serializers.ValidationError({
                "error": f"Failed to create purchase: {str(e)}"
            })


    def update(self, instance, validated_data):
        items_data = validated_data.pop('purchase_items', None)
        instant_pay = validated_data.pop('instant_pay', False)
        account = validated_data.get('account', instance.account)
        payment_method = validated_data.get('payment_method', instance.payment_method)
        
        with db_transaction.atomic():
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
            
            # Update totals after item changes
            instance.update_totals(force_update=True)
            
            # Handle instant payment
            if instant_pay and account and payment_method and instance.grand_total > 0:
                instance.instant_pay(payment_method, account)
            
            return instance


    
    # Add this method to ensure proper representation
    def to_representation(self, instance):
        """Custom representation to include calculated fields"""
        representation = super().to_representation(instance)
        
        # Ensure we have the latest data by refreshing from DB
        instance.refresh_from_db()
        
        # Force update totals to ensure calculations are current
        instance.update_totals(force_update=True)
        
        # Add payment breakdown with fresh data
        representation['payment_breakdown'] = instance.get_payment_breakdown()
        
        # Ensure all calculated fields are included
        representation['grand_total'] = float(instance.grand_total)
        representation['total'] = float(instance.total)
        representation['due_amount'] = float(instance.due_amount)
        representation['paid_amount'] = float(instance.paid_amount)
        representation['change_amount'] = float(instance.change_amount)
        
        # Add item count and total quantity
        representation['item_count'] = instance.item_count
        representation['total_quantity'] = instance.total_quantity
        
        return representation

    def create(self, validated_data):
        try:
            request = self.context.get('request')
            if not request or not hasattr(request.user, 'company') or not request.user.company:
                raise serializers.ValidationError("User does not belong to a company.")

            items_data = validated_data.pop('purchase_items', [])
            instant_pay = validated_data.pop('instant_pay', False)
            
            account = validated_data.get('account', None)
            payment_method = validated_data.get('payment_method', None)
            paid_amount = validated_data.get('paid_amount', Decimal('0.00'))
            
            validated_data['company'] = request.user.company
            validated_data['created_by'] = request.user

            with db_transaction.atomic():
                # Create purchase first (without items)
                purchase = Purchase.objects.create(**validated_data)
                logger.info(f"✅ Created purchase ID: {purchase.id} for supplier ID: {purchase.supplier_id}")

                # Create purchase items
                created_items = []
                for item_data in items_data:
                    item = PurchaseItem.objects.create(purchase=purchase, **item_data)
                    created_items.append(item)
                    logger.info(f"📦 Created item: {item.product.name} x {item.qty} @ {item.price}")

                # Update totals to calculate the actual totals
                logger.info(f"🔄 Calling update_totals for purchase {purchase.id}")
                purchase.update_totals(force_update=True)
                
                # Refresh from database to get updated values
                purchase.refresh_from_db()
                logger.info(f"📊 Final purchase totals - Total: {purchase.total}, Grand Total: {purchase.grand_total}, Paid: {purchase.paid_amount}")

                # Handle payments - FIXED: Use the purchase's paid_amount field
                if paid_amount > 0:
                    logger.info(f"💰 Processing payment amount: {paid_amount}")
                    # Update the purchase's paid_amount field directly
                    purchase.paid_amount = paid_amount
                    purchase.due_amount = max(Decimal('0.00'), purchase.grand_total - paid_amount)
                    purchase._update_payment_status()
                    
                    # Save the payment updates
                    purchase.save(update_fields=['paid_amount', 'due_amount', 'payment_status', 'date_updated'])
                    
                    # Create transaction if account and payment method provided
                    if account and payment_method:
                        logger.info(f"💰 Creating payment transaction: {paid_amount}")
                        from transactions.models import Transaction
                        transaction_obj = Transaction.create_for_purchase_payment(
                            purchase=purchase,
                            amount=paid_amount,
                            payment_method=payment_method,
                            account=account,
                            created_by=request.user
                        )
                        if transaction_obj:
                            logger.info(f"✅ Payment transaction created: {transaction_obj.transaction_no}")

                # Update supplier totals
                if purchase.supplier:
                    logger.info(f"🔄 Updating supplier totals for {purchase.supplier.name}")
                    purchase.supplier.update_purchase_totals()

            # Final refresh to ensure all data is current
            purchase.refresh_from_db()
            logger.info(f"🎉 Purchase creation completed successfully. ID: {purchase.id}, Invoice: {purchase.invoice_no}")
            logger.info(f"💰 Final amounts - Grand Total: {purchase.grand_total}, Paid: {purchase.paid_amount}, Due: {purchase.due_amount}")
            
            return purchase
            
        except Exception as e:
            logger.exception("❌ Exception in PurchaseSerializer.create")
            raise serializers.ValidationError({
                "error": f"Failed to create purchase: {str(e)}"
            })