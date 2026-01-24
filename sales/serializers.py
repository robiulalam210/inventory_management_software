# sales/serializers.py (UPDATED)

from rest_framework import serializers
from .models import Sale, SaleItem
from products.models import Product, SaleMode, ProductSaleMode
from accounts.models import Account
from customers.models import Customer
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class SaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    # Sale mode fields
    sale_mode_id = serializers.PrimaryKeyRelatedField(
        queryset=SaleMode.objects.all(),
        source='sale_mode',
        required=False,
        allow_null=True
    )
    sale_mode_name = serializers.CharField(source='sale_mode.name', read_only=True)
    
    # Quantity fields - accept BOTH quantity and sale_quantity for backward compatibility
    quantity = serializers.DecimalField(
        max_digits=12, 
        decimal_places=3,
        required=False,  # Optional if sale_quantity provided
        min_value=Decimal('0.001'),
        write_only=True
    )
    sale_quantity = serializers.DecimalField(
        max_digits=12, 
        decimal_places=3,
        required=False,  # Optional if quantity provided
        min_value=Decimal('0.001'),
        write_only=True
    )
    
    base_quantity = serializers.DecimalField(
        max_digits=12, 
        decimal_places=3,
        read_only=True
    )
    
    # Price fields
    price_type = serializers.CharField(read_only=True)
    flat_price = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2,
        required=False,
        allow_null=True
    )
    
    subtotal = serializers.SerializerMethodField()
    
    # Accept client aliases and normalize to model choices ('fixed'|'percent')
    discount_type = serializers.CharField(required=False, default='fixed')

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_id', 'product_name', 'product_sku',
            'sale_mode_id', 'sale_mode_name',
            'quantity', 'sale_quantity', 'base_quantity',
            'unit_price', 'price_type', 'flat_price',
            'discount', 'discount_type', 'subtotal'
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'sale_mode_name',
            'base_quantity', 'price_type', 'subtotal'
        ]

    def validate_discount_type(self, value):
        """Normalize and validate discount_type values from clients."""
        if value is None or value == '':
            return 'fixed'
        if not isinstance(value, str):
            raise serializers.ValidationError('Invalid discount_type.')

        v = value.strip().lower()
        # Accept "percentage" from clients, normalize to model's "percent"
        if v == 'percentage':
            return 'percent'
        if v in ('percent', 'fixed'):
            return v

        raise serializers.ValidationError('Invalid discount_type. Allowed: fixed, percent, percentage')

    def validate(self, data):
        """Validate sale item with sale mode and handle backward compatibility"""
        product = data.get('product')
        sale_mode = data.get('sale_mode')
        
        # Handle backward compatibility: use sale_quantity if provided, otherwise use quantity
        quantity = data.get('quantity')
        sale_quantity = data.get('sale_quantity')
        
        if sale_quantity is not None:
            # Use sale_quantity if provided (new way)
            final_quantity = sale_quantity
            # Remove sale_quantity from validated data as it will be saved as quantity
            data.pop('sale_quantity', None)
        elif quantity is not None:
            # Use quantity if provided (old way)
            final_quantity = quantity
        else:
            # Neither provided, use default
            final_quantity = Decimal('1.00')
        
        # Set the quantity in validated data
        data['quantity'] = final_quantity
        
        # If no sale mode specified, use product's base unit or keep None for normal products
        if not sale_mode and product and product.unit:
            try:
                # Try to find a default sale mode for this unit
                sale_mode = SaleMode.objects.filter(
                    base_unit=product.unit,
                    conversion_factor=Decimal('1.00'),
                    price_type='unit'
                ).first()
                if sale_mode:
                    data['sale_mode'] = sale_mode
            except Exception:
                # If no sale mode found, product will be sold in normal mode
                pass
        
        # Validate stock if sale mode is provided
        if sale_mode and product:
            try:
                base_quantity = sale_mode.convert_to_base(final_quantity)
            except:
                # If convert_to_base fails, use quantity as base
                base_quantity = final_quantity
        else:
            # For normal products without sale mode
            base_quantity = final_quantity
        
        # Check stock
        if product and base_quantity > Decimal(str(product.stock_qty)):
            raise serializers.ValidationError({
                'quantity': f"Insufficient stock. Available: {product.stock_qty} {product.unit.name if product.unit else 'units'}, "
                          f"Requested: {final_quantity} {sale_mode.name if sale_mode else product.unit.name if product.unit else 'units'}"
            })
        
        # Get unit price if not provided
        if 'unit_price' not in data or not data['unit_price']:
            if sale_mode:
                try:
                    product_sale_mode = ProductSaleMode.objects.get(
                        product=product,
                        sale_mode=sale_mode,
                        is_active=True
                    )
                    
                    if sale_mode.price_type == 'flat' and product_sale_mode.flat_price:
                        data['flat_price'] = product_sale_mode.flat_price
                        data['unit_price'] = product_sale_mode.flat_price / final_quantity if final_quantity else Decimal('0.00')
                    elif sale_mode.price_type == 'tier':
                        data['unit_price'] = product_sale_mode.get_tier_price(base_quantity)
                    else:
                        data['unit_price'] = product_sale_mode.get_unit_price()
                        
                except ProductSaleMode.DoesNotExist:
                    # Fallback to product selling price
                    data['unit_price'] = product.selling_price
            else:
                # For normal products without sale mode
                data['unit_price'] = product.selling_price
        
        return data

    def get_subtotal(self, obj):
        return float(obj.subtotal()) if obj.subtotal() else 0.0
    
    def to_representation(self, instance):
        """Add sale_quantity to output for backward compatibility"""
        representation = super().to_representation(instance)
        representation['sale_quantity'] = representation.get('quantity', 0)
        return representation


class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='customer',
        required=False,
        allow_null=True
    )
    customer_name = serializers.CharField(read_only=True)
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
    
    # Sale items with multi-mode support
    items = SaleItemSerializer(many=True, write_only=True)
    
    # Read-only calculated fields
    gross_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal('0.00'))
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    change_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)
    invoice_no = serializers.CharField(read_only=True)
    sale_date = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'invoice_no', 'customer_id', 'customer_name', 'customer_type',
            'sale_type', 'sale_date', 'sale_by', 'sale_by_name', 'created_by_name',
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'paid_amount', 'due_amount', 'change_amount',
            'overall_discount', 'overall_discount_type',
            'overall_delivery_charge', 'overall_delivery_type',
            'overall_service_charge', 'overall_service_type',
            'overall_vat_amount', 'overall_vat_type',
            'payment_method', 'account_id', 'account_name',
            'with_money_receipt', 'remark', 'items', 'payment_status'
        ]
        read_only_fields = [
            'id', 'invoice_no', 'sale_date', 'payment_status',
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'due_amount', 'change_amount', 'created_by_name', 'sale_by_name'
        ]

    def validate(self, attrs):
        """Validate sale-level data with multi-mode support"""
        items = attrs.get('items', [])
        
        if not items:
            raise serializers.ValidationError({'items': 'At least one item is required.'})
        
        # Validate each item has required fields
        for i, item in enumerate(items):
            if 'product' not in item:
                raise serializers.ValidationError({
                    'items': f'Item {i+1}: Product is required'
                })
            
            # Check for either quantity or sale_quantity
            quantity = item.get('quantity')
            sale_quantity = item.get('sale_quantity')
            
            if quantity is None and sale_quantity is None:
                raise serializers.ValidationError({
                    'items': f'Item {i+1}: Either quantity or sale_quantity is required'
                })
            
            final_quantity = sale_quantity if sale_quantity is not None else quantity
            if final_quantity <= 0:
                raise serializers.ValidationError({
                    'items': f'Item {i+1}: Quantity must be greater than 0'
                })
        
        return attrs

    def create(self, validated_data):
        """
        Create sale with multi-mode items and backward compatibility
        """
        items_data = validated_data.pop('items', [])

        # Attach metadata from request user if available
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            if 'sale_by' not in validated_data or not validated_data['sale_by']:
                validated_data['sale_by'] = request.user
            if hasattr(request.user, 'company') and request.user.company:
                validated_data['company'] = request.user.company

        # Handle walk-in defaults
        if validated_data.get('customer_type') == 'walk_in':
            validated_data['customer'] = None
            validated_data.setdefault('customer_name', 'Walk-in Customer')

        try:
            with transaction.atomic():
                # Create the sale
                sale = Sale.objects.create(**validated_data)

                # Create items with backward compatibility
                for item_data in items_data:
                    # Ensure quantity field is set (handles sale_quantity to quantity conversion)
                    if 'sale_quantity' in item_data and 'quantity' not in item_data:
                        item_data['quantity'] = item_data.pop('sale_quantity')
                    
                    SaleItem.objects.create(sale=sale, **item_data)

                # Recalculate totals
                sale.calculate_totals()
                sale.refresh_from_db()
                return sale

        except serializers.ValidationError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error while creating sale")
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})

    def to_representation(self, instance):
        """Return sale representation including item details"""
        rep = super().to_representation(instance)
        
        # Add item details with sale_quantity field for backward compatibility
        rep['items'] = SaleItemSerializer(instance.items.all(), many=True).data
        rep['customer_name'] = instance.get_customer_display()

        # Convert Decimal fields to float
        decimal_fields = [
            'gross_total', 'net_total', 'grand_total', 'payable_amount',
            'paid_amount', 'due_amount', 'change_amount',
            'overall_discount', 'overall_delivery_charge',
            'overall_service_charge', 'overall_vat_amount'
        ]
        for field in decimal_fields:
            if field in rep and rep[field] is not None:
                rep[field] = float(rep[field])
                
        return rep