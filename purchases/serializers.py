import logging
import traceback
from rest_framework import serializers
from .models import Purchase, PurchaseItem
from products.models import Product
from accounts.models import Account
from django.db import transaction as db_transaction
from decimal import Decimal
from django.apps import apps  # ADD THIS IMPORT

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
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value

    def validate_qty(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value


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
        user = request.user if request else None
        
        # Validate purchase items for creation
        if request and getattr(request, "method", None) == 'POST':
            purchase_items = attrs.get('purchase_items') or []
            if not purchase_items:
                raise serializers.ValidationError({"purchase_items": "At least one purchase item is required."})
            
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
            if not attrs.get('paid_amount') or Decimal(str(attrs.get('paid_amount', 0))) <= 0:
                raise serializers.ValidationError({
                    "paid_amount": "Paid amount must be greater than 0 for instant payment."
                })
        
        # Validate amounts
        overall_discount = attrs.get('overall_discount', 0)
        if overall_discount < 0:
            raise serializers.ValidationError({
                "overall_discount": "Discount cannot be negative."
            })
        
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
        """Create purchase with transaction - FIXED to prevent duplicates"""
        try:
            request = self.context.get('request')
            user = request.user if request else None
            
            if not user or not hasattr(user, 'company') or not user.company:
                raise serializers.ValidationError({"error": "User does not belong to a company."})

            items_data = validated_data.pop('purchase_items', [])
            instant_pay = validated_data.pop('instant_pay', False)
            
            account = validated_data.get('account', None)
            payment_method = validated_data.get('payment_method', None)
            paid_amount = validated_data.get('paid_amount', Decimal('0.00'))
            
            logger.info(f"INFO: Creating purchase with data:")
            logger.info(f"  User: {user.username}")
            logger.info(f"  Company: {user.company.name}")
            logger.info(f"  Instant Pay: {instant_pay}")
            logger.info(f"  Paid Amount: {paid_amount}")
            logger.info(f"  Account: {account.name if account else 'None'}")
            logger.info(f"  Payment Method: {payment_method}")
            logger.info(f"  Items Count: {len(items_data)}")

            validated_data['company'] = user.company
            validated_data['created_by'] = user

            purchase = None
            
            with db_transaction.atomic():
                # Create purchase first (without items)
                purchase = Purchase.objects.create(**validated_data)
                logger.info(f"SUCCESS: Purchase created - Invoice: {purchase.invoice_no}, ID: {purchase.id}")
                
                # Create purchase items
                for item_data in items_data:
                    PurchaseItem.objects.create(purchase=purchase, **item_data)
                logger.info(f"SUCCESS: Created {len(items_data)} purchase items")

                # Update totals to calculate the actual totals
                purchase.update_totals(force_update=True)
                logger.info(f"INFO: Purchase totals updated - Grand Total: {purchase.grand_total}")
                
                # FIXED: Handle instant payment - ONLY create transaction if needed
                if instant_pay and paid_amount > 0 and account and payment_method:
                    logger.info(f"INFO: Processing instant payment for purchase {purchase.invoice_no}")
                    logger.info(f"  Amount to pay: {paid_amount}")
                    
                    # Check if transaction already exists before creating
                    Transaction = apps.get_model('transactions', 'Transaction')
                    existing_transaction = Transaction.objects.filter(
                        purchase=purchase,
                        amount=paid_amount,
                        transaction_type='debit',
                        account=account,
                        payment_method=payment_method,
                        status='completed'
                    ).first()
                    
                    if existing_transaction:
                        logger.warning(f"WARNING: Transaction already exists: {existing_transaction.transaction_no}")
                        # Just update the purchase with payment details
                        purchase.paid_amount = paid_amount
                        purchase.account = account
                        purchase.payment_method = payment_method
                        purchase.update_totals(force_update=True)
                    else:
                        # Update purchase with payment details
                        purchase.paid_amount = paid_amount
                        purchase.account = account
                        purchase.payment_method = payment_method
                        purchase.save(update_fields=['paid_amount', 'account', 'payment_method', 'date_updated'])
                        
                        # Update totals again to recalculate due_amount
                        purchase.update_totals(force_update=True)
                        
                        # Create transaction (ONLY HERE - not in multiple places)
                        transaction = purchase.create_initial_payment_transaction()
                        if transaction:
                            logger.info(f"SUCCESS: Payment transaction created: {transaction.transaction_no}")
                        else:
                            logger.warning(f"WARNING: Failed to create payment transaction")
                
                # Refresh purchase to get updated values
                purchase.refresh_from_db()
                logger.info(f"INFO: Final purchase state - Paid: {purchase.paid_amount}, Due: {purchase.due_amount}, Status: {purchase.payment_status}")

            return purchase
            
        except serializers.ValidationError as e:
            logger.error(f"VALIDATION ERROR: {e.detail}")
            raise e
        except Exception as e:
            logger.exception("ERROR: Exception in PurchaseSerializer.create")
            raise serializers.ValidationError({
                "error": f"Failed to create purchase: {str(e)}"
            })

    def to_representation(self, instance):
        """Custom representation to include calculated fields"""
        representation = super().to_representation(instance)
        
        # Force update totals to ensure calculations are current
        try:
            instance.update_totals(force_update=True)
        except Exception as e:
            logger.error(f"ERROR: Failed to update totals in to_representation: {str(e)}")
        
        # Add payment breakdown with fresh data
        try:
            representation['payment_breakdown'] = instance.get_payment_breakdown()
        except Exception as e:
            logger.error(f"ERROR: Failed to get payment breakdown: {str(e)}")
            representation['payment_breakdown'] = {}
        
        # Ensure all calculated fields are included
        representation['grand_total'] = float(instance.grand_total)
        representation['total'] = float(instance.total)
        representation['due_amount'] = float(instance.due_amount)
        representation['paid_amount'] = float(instance.paid_amount)
        representation['change_amount'] = float(instance.change_amount)
        
        # Add item count and total quantity
        representation['item_count'] = instance.item_count
        representation['total_quantity'] = instance.total_quantity
        
        # Add transaction info if available
        try:
            if instance.paid_amount > 0:
                Transaction = apps.get_model('transactions', 'Transaction')
                transactions = Transaction.objects.filter(purchase=instance, status='completed')
                representation['transactions'] = [
                    {
                        'id': t.id,
                        'transaction_no': t.transaction_no,
                        'amount': float(t.amount),
                        'type': t.transaction_type,
                        'created_at': t.created_at.isoformat() if t.created_at else None
                    }
                    for t in transactions
                ]
                representation['transaction_count'] = transactions.count()
        except Exception as e:
            logger.error(f"ERROR: Failed to fetch transactions: {str(e)}")
            representation['transactions'] = []
            representation['transaction_count'] = 0
        
        return representation