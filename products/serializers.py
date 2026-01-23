from rest_framework import serializers
from django.conf import settings
from django.db import transaction, IntegrityError
import time
import random
from decimal import Decimal, InvalidOperation  # ADD THIS IMPORT

import re
import json
from .models import Category, Unit, Brand, Group, Source, Product, ProductSaleMode, SaleMode, PriceTier
from sales.models import Sale, SaleItem  # Assuming you have these models


# Define a fallback CompanyProductSequence class
class CompanyProductSequence:
    """Fallback CompanyProductSequence class for SKU generation"""
    @classmethod
    def get_next_sequence(cls, company):
        """Get next sequence number for a company"""
        try:
            # First try to import the real model
            from .models import CompanyProductSequence as RealSequence
            return RealSequence.get_next_sequence(company)
        except (ImportError, AttributeError):
            # Fallback: use timestamp-based sequence
            import time
            timestamp = int(time.time())
            return timestamp % 1000000 + 1000


class CleanedChoiceField(serializers.ChoiceField):
    """Custom ChoiceField that cleans quoted strings BEFORE any validation"""
    
    def __init__(self, **kwargs):
        # Set allow_blank to True by default to handle empty strings
        kwargs.setdefault('allow_blank', True)
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        """Clean the data before validation"""
        if data is not None:
            # Convert to string if it isn't already
            if not isinstance(data, str):
                data = str(data)
            
            # Clean the string - remove quotes and whitespace, convert to lowercase
            data = re.sub(r'["\']', '', data).strip().lower()
            
            # Map common variations
            value_mapping = {
                'percent': 'percentage',
                'pct': 'percentage',
                'perc': 'percentage',
                'fixed_amount': 'fixed',
                'flat': 'fixed',
                'percentage': 'percentage',  # Explicit mapping
                'fixed': 'fixed',  # Explicit mapping
            }
            
            # Apply mapping if needed
            if data in value_mapping:
                data = value_mapping[data]
            
            # Handle empty string after cleaning
            if data == '':
                data = None
        
        # Now run the parent validation with cleaned data
        return super().to_internal_value(data)


class CategorySerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Category
        fields = '__all__'


class UnitSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Unit
        fields = '__all__'


class BrandSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Brand
        fields = '__all__'


class GroupSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Group
        fields = '__all__'


class SourceSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Source
        fields = '__all__'


class PriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceTier
        fields = ['id', 'min_quantity', 'max_quantity', 'price']
        read_only_fields = ['id']
# products/serializers.py - Update ProductSaleModeSerializer

class ProductSaleModeSerializer(serializers.ModelSerializer):
    tiers = PriceTierSerializer(many=True, read_only=True)
    sale_mode_name = serializers.CharField(source='sale_mode.name', read_only=True)
    sale_mode_code = serializers.CharField(source='sale_mode.code', read_only=True)
    price_type = serializers.CharField(source='sale_mode.price_type', read_only=True)
    conversion_factor = serializers.DecimalField(
        source='sale_mode.conversion_factor', 
        max_digits=12, 
        decimal_places=6,
        read_only=True
    )
    
    # Make these fields write-only
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        required=True
    )
    sale_mode = serializers.PrimaryKeyRelatedField(
        queryset=SaleMode.objects.all(),
        write_only=True,
        required=True
    )
    
    # Add read-only display fields
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = ProductSaleMode
        fields = [
            'id', 'product', 'product_name', 'product_sku', 
            'sale_mode', 'sale_mode_name', 'sale_mode_code',
            'unit_price', 'flat_price', 'price_type', 'conversion_factor',
            'discount_type', 'discount_value', 'is_active',
            'tiers', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate the data"""
        request = self.context.get('request')
        
        # Get product and sale mode
        product = data.get('product')
        sale_mode = data.get('sale_mode')
        
        if not product or not sale_mode:
            raise serializers.ValidationError("Product and SaleMode are required")
        
        # Check if product belongs to user's company
        if request and hasattr(request.user, 'company'):
            if product.company != request.user.company:
                raise serializers.ValidationError("Product does not belong to your company")
            
            if sale_mode.company != request.user.company:
                raise serializers.ValidationError("SaleMode does not belong to your company")
        
        # Check if already exists
        if ProductSaleMode.objects.filter(product=product, sale_mode=sale_mode).exists():
            raise serializers.ValidationError("Sale mode already configured for this product")
        
        # Validate units match
        if sale_mode.base_unit != product.unit:
            raise serializers.ValidationError(
                f"Sale mode base unit ({sale_mode.base_unit.name}) doesn't match product unit ({product.unit.name})"
            )
        
        return data
    
    def to_internal_value(self, data):
        """Handle field name conversions"""
        data = data.copy()
        
        # Convert product_id to product
        if 'product_id' in data and 'product' not in data:
            data['product'] = data.pop('product_id')
        
        # Convert sale_mode_id to sale_mode (if needed)
        if 'sale_mode_id' in data and 'sale_mode' not in data:
            data['sale_mode'] = data.pop('sale_mode_id')
        
        return super().to_internal_value(data)

# products/serializers.py - Update SaleModeSerializer

class SaleModeSerializer(serializers.ModelSerializer):
    base_unit_name = serializers.CharField(source='base_unit.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = SaleMode
        fields = [
            'id', 'name', 'code', 'base_unit', 'base_unit_name',
            'conversion_factor', 'price_type', 'is_active', 
            'company', 'company_name', 'created_by', 'created_by_name'
            # Remove 'created_at' and 'updated_at' since they don't exist in model
        ]
        read_only_fields = ['id', 'company', 'created_by']  # Remove 'created_at', 'updated_at'
    
    def validate_base_unit(self, value):
        """Validate base_unit exists and belongs to user's company"""
        request = self.context.get('request')
        
        if not value:
            raise serializers.ValidationError("Base unit is required")
        
        # Check if unit belongs to user's company
        if request and hasattr(request.user, 'company'):
            if value.company != request.user.company:
                raise serializers.ValidationError(
                    "Unit does not belong to your company"
                )
        
        return value
    
    def validate_conversion_factor(self, value):
        """Validate conversion factor"""
        if value <= 0:
            raise serializers.ValidationError(
                "Conversion factor must be greater than 0"
            )
        return value
    
    def create(self, validated_data):
        """Override create to ensure company is set"""
        request = self.context.get('request')
        
        # Set company from user or base_unit
        if request and hasattr(request.user, 'company'):
            validated_data['company'] = request.user.company
        elif 'base_unit' in validated_data:
            validated_data['company'] = validated_data['base_unit'].company
        
        # Set created_by if user is authenticated
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class ProductDetailSerializer(serializers.ModelSerializer):
    """Extended product serializer with sale modes"""
    sale_modes = ProductSaleModeSerializer(source='sale_modes.filter(is_active=True)', many=True, read_only=True)
    available_sale_modes = serializers.SerializerMethodField()
    base_unit_name = serializers.CharField(source='unit.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'company', 'created_by',
            'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock',
            'stock_qty', 'alert_quantity', 'description', 'image',
            'is_active', 'discount_type', 'discount_value',
            'discount_applied_on', 'created_at', 'updated_at',
            'stock_status', 'final_price',
            # Sale mode fields
            'sale_modes', 'available_sale_modes', 'base_unit_name'
        ]
        read_only_fields = [
            'id', 'company', 'created_by', 'sku', 'stock_status',
            'final_price', 'created_at', 'updated_at'
        ]
    
    def get_available_sale_modes(self, obj):
        """Get all available sale modes for this product type"""
        from .models import SaleMode
        
        # Get all sale modes that use the same base unit as product
        sale_modes = SaleMode.objects.filter(
            base_unit=obj.unit,
            is_active=True
        ).values('id', 'name', 'code', 'price_type', 'conversion_factor')
        
        # Add current configuration status
        for mode in sale_modes:
            try:
                product_sale_mode = ProductSaleMode.objects.get(
                    product=obj,
                    sale_mode_id=mode['id']
                )
                mode['configured'] = True
                mode['is_active'] = product_sale_mode.is_active
                mode['unit_price'] = float(product_sale_mode.unit_price) if product_sale_mode.unit_price else None
                mode['flat_price'] = float(product_sale_mode.flat_price) if product_sale_mode.flat_price else None
            except ProductSaleMode.DoesNotExist:
                mode['configured'] = False
                mode['is_active'] = False
                mode['unit_price'] = None
                mode['flat_price'] = None
        
        return list(sale_modes)


class ProductCreateSerializer(serializers.ModelSerializer):
    # Add discount fields to the serializer - use our custom CleanedChoiceField
    discount_type = CleanedChoiceField(
        choices=Product.DISCOUNT_TYPE_CHOICES,
        required=False,
        allow_null=True
    )
    discount_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal('0.00')
    )
    discount_applied_on = serializers.BooleanField(
        required=False,
        default=False
    )
    
    # Make foreign key fields optional for creation
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=True
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(),
        required=True
    )
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(),
        required=False,
        allow_null=True
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        required=False,
        allow_null=True
    )
    source = serializers.PrimaryKeyRelatedField(
        queryset=Source.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock', 
            'alert_quantity', 'description', 'image', 'is_active',
            'discount_type', 'discount_value', 'discount_applied_on'
        ]
        extra_kwargs = {
            'purchase_price': {'default': Decimal('0.00')},
            'selling_price': {'default': Decimal('0.00')},
            'opening_stock': {'default': 0},
            'alert_quantity': {'default': 5},
            'is_active': {'default': True},
        }

    def to_internal_value(self, data):
        """
        Convert incoming data before validation
        Handle field name mismatches and type conversions
        """
        if isinstance(data, dict):
            data = data.copy()
            
            # Handle 'groups' to 'group' mapping
            if 'groups' in data and 'group' not in data:
                data['group'] = data.pop('groups')
            
            # Handle discount_applied_on string to boolean conversion
            if 'discount_applied_on' in data:
                value = data['discount_applied_on']
                if isinstance(value, str):
                    value = value.strip().lower()
                    data['discount_applied_on'] = value in ['true', '1', 'yes', 'on']
                elif isinstance(value, bool):
                    data['discount_applied_on'] = value
        
        return super().to_internal_value(data)

    def validate_name(self, value):
        """Ensure product name is unique within company"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            if Product.objects.filter(
                company=request.user.company, 
                name=value
            ).exists():
                raise serializers.ValidationError(
                    "A product with this name already exists in your company."
                )
        return value

    def validate(self, data):
        """
        Custom validation for product data
        """
        purchase_price = data.get('purchase_price', Decimal('0.00'))
        selling_price = data.get('selling_price', Decimal('0.00'))
        
        if selling_price < purchase_price:
            raise serializers.ValidationError({
                "selling_price": "Selling price cannot be less than purchase price"
            })
        
        opening_stock = data.get('opening_stock', 0)
        if opening_stock < 0:
            raise serializers.ValidationError({
                "opening_stock": "Opening stock cannot be negative"
            })
        
        alert_quantity = data.get('alert_quantity', 5)
        if alert_quantity < 0:
            raise serializers.ValidationError({
                "alert_quantity": "Alert quantity cannot be negative"
            })
        
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        discount_applied_on = data.get('discount_applied_on', False)
        
        if discount_applied_on:
            if not discount_type:
                raise serializers.ValidationError({
                    "discount_type": "Discount type is required when discount is applied"
                })
            if not discount_value:
                raise serializers.ValidationError({
                    "discount_value": "Discount value is required when discount is applied"
                })
            if discount_value and discount_value < Decimal('0.00'):
                raise serializers.ValidationError({
                    "discount_value": "Discount value cannot be negative"
                })
        else:
            if discount_type or discount_value:
                data['discount_type'] = None
                data['discount_value'] = None
        
        return data

    def create(self, validated_data):
        """
        Create product with automatic SKU generation and company assignment
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        company = getattr(request.user, 'company', None)
        if not company:
            raise serializers.ValidationError("User must be associated with a company")
        validated_data['company'] = company

        validated_data['created_by'] = request.user

        opening_stock = validated_data.get('opening_stock', 0)
        validated_data['stock_qty'] = opening_stock

        # Generate SKU
        if not validated_data.get('sku'):
            try:
                next_num = CompanyProductSequence.get_next_sequence(company)
                validated_data['sku'] = f"PDT-{company.id}-{next_num}"
            except Exception as e:
                timestamp = int(time.time())
                random_suffix = random.randint(100, 999)
                company_id = company.id
                validated_data['sku'] = f"PDT-{company_id}-FB{timestamp}{random_suffix}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    product = Product.objects.create(**validated_data)
                return product
            except IntegrityError as e:
                if 'sku' in str(e).lower() and attempt < max_retries - 1:
                    timestamp = int(time.time())
                    random_suffix = random.randint(100, 999)
                    validated_data['sku'] = f"PDT-{company.id}-{timestamp}{random_suffix}"
                    continue
                else:
                    if 'unique_company_product_name' in str(e):
                        raise serializers.ValidationError({
                            'name': 'A product with this name already exists in your company.'
                        })
                    elif 'sku' in str(e).lower():
                        raise serializers.ValidationError({
                            'sku': f'Could not generate unique SKU after {max_retries} attempts. Please try again.'
                        })
                    else:
                        raise


class ProductUpdateSerializer(serializers.ModelSerializer):
    discount_type = CleanedChoiceField(
        choices=Product.DISCOUNT_TYPE_CHOICES,
        required=False,
        allow_null=True
    )
    discount_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal('0.00')
    )
    discount_applied_on = serializers.BooleanField(required=False)
    
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(),
        required=False
    )
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(),
        required=False,
        allow_null=True
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        required=False,
        allow_null=True
    )
    source = serializers.PrimaryKeyRelatedField(
        queryset=Source.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'alert_quantity', 
            'description', 'image', 'is_active',
            'discount_type', 'discount_value', 'discount_applied_on'
        ]

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.copy()
            
            # Handle 'groups' to 'group' mapping
            if 'groups' in data and 'group' not in data:
                data['group'] = data.pop('groups')
            
            # Handle discount_applied_on string to boolean conversion
            if 'discount_applied_on' in data:
                value = data['discount_applied_on']
                if isinstance(value, str):
                    value = value.strip().lower()
                    data['discount_applied_on'] = value in ['true', '1', 'yes', 'on']
                elif isinstance(value, bool):
                    data['discount_applied_on'] = value
        
        return super().to_internal_value(data)

    def validate_name(self, value):
        request = self.context.get('request')
        instance = self.instance
        
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            if Product.objects.filter(
                company=request.user.company, 
                name=value
            ).exclude(id=instance.id).exists():
                raise serializers.ValidationError(
                    "A product with this name already exists in your company."
                )
        return value

    def validate(self, data):
        errors = {}

        instance = self.instance
        purchase_price = data.get('purchase_price', instance.purchase_price if instance else Decimal('0.00'))
        selling_price = data.get('selling_price', instance.selling_price if instance else Decimal('0.00'))
        
        if selling_price < purchase_price:
            errors['selling_price'] = "Selling price cannot be less than purchase price"
        
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        discount_applied_on = data.get('discount_applied_on', 
                                     instance.discount_applied_on if instance else False)
        
        if discount_applied_on:
            if not discount_type:
                discount_type = instance.discount_type if instance else None
            if not discount_value:
                discount_value = instance.discount_value if instance else None
                
            if not discount_type:
                errors['discount_type'] = "Discount type is required when discount is applied"
            if not discount_value:
                errors['discount_value'] = "Discount value is required when discount is applied"
            elif discount_value and discount_value < Decimal('0.00'):
                errors['discount_value'] = "Discount value cannot be negative"
        else:
            data['discount_type'] = None
            data['discount_value'] = None
            data['discount_applied_on'] = False

        if errors:
            raise serializers.ValidationError(errors)

        return data
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class ProductSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(),
        required=False
    )
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(),
        required=False,
        allow_null=True
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        required=False,
        allow_null=True
    )
    source = serializers.PrimaryKeyRelatedField(
        queryset=Source.objects.all(),
        required=False,
        allow_null=True
    )
    
    category_info = serializers.SerializerMethodField(read_only=True)
    unit_info = serializers.SerializerMethodField(read_only=True)
    brand_info = serializers.SerializerMethodField(read_only=True)
    group_info = serializers.SerializerMethodField(read_only=True)
    source_info = serializers.SerializerMethodField(read_only=True)
    created_by_info = serializers.SerializerMethodField(read_only=True)
    stock_status = serializers.ReadOnlyField()
    stock_status_display = serializers.SerializerMethodField(read_only=True)

    discount_type = CleanedChoiceField(
        choices=Product.DISCOUNT_TYPE_CHOICES,
        required=False,
        allow_null=True
    )
    discount_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal('0.00')
    )
    discount_applied_on = serializers.BooleanField(required=False, default=False)
    
    discount_applied = serializers.BooleanField(source='discount_applied_on', read_only=True)
    final_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'company', 'created_by', 'name', 'sku', 
            'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock', 
            'stock_qty', 'alert_quantity', 'description', 'image',
            'is_active', 'created_at', 'updated_at',
            'category_info', 'unit_info', 'brand_info', 'group_info', 
            'source_info', 'created_by_info', 'stock_status', 'stock_status_display',
            'discount_type', 'discount_value', 'discount_applied_on',
            'discount_applied', 'final_price'
        ]
        read_only_fields = [
            'id', 'company', 'created_by', 'created_at', 'updated_at', 
            'sku', 'stock_status', 'stock_qty', 'final_price'
        ]

    def get_category_info(self, obj):
        if obj.category:
            return {'id': obj.category.id, 'name': obj.category.name}
        return None

    def get_unit_info(self, obj):
        if obj.unit:
            return {'id': obj.unit.id, 'name': obj.unit.name, 'code': obj.unit.code}
        return None

    def get_brand_info(self, obj):
        if obj.brand:
            return {'id': obj.brand.id, 'name': obj.brand.name}
        return None

    def get_group_info(self, obj):
        if obj.group:
            return {'id': obj.group.id, 'name': obj.group.name}
        return None

    def get_source_info(self, obj):
        if obj.source:
            return {'id': obj.source.id, 'name': obj.source.name}
        return None

    def get_created_by_info(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id, 
                'username': obj.created_by.username,
                'email': obj.created_by.email
            }
        return None

    def get_stock_status_display(self, obj):
        status_map = {
            'out_of_stock': 'Out of Stock',
            'low_stock': 'Low Stock', 
            'in_stock': 'In Stock'
        }
        return status_map.get(obj.stock_status, 'Unknown')

    def validate(self, data):
        discount_applied_on = data.get('discount_applied_on', False)
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        
        if discount_applied_on:
            if not discount_type:
                raise serializers.ValidationError({
                    "discount_type": "Discount type is required when discount is applied"
                })
            if not discount_value:
                raise serializers.ValidationError({
                    "discount_value": "Discount value is required when discount is applied"
                })
        
        return data