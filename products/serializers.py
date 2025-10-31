from rest_framework import serializers
from django.conf import settings
from django.db import transaction, IntegrityError
import time
import random
from .models import Category, Unit, Brand, Group, Source, Product

# Try to import CompanyProductSequence if you implemented it in models.py.
try:
    from .models import CompanyProductSequence
except Exception:
    CompanyProductSequence = None


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



class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock', 
            'alert_quantity', 'description', 'image', 'is_active'
        ]

    def validate_name(self, value):
        """Ensure product name is unique within company"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            if Product.objects.filter(company=request.user.company, name=value).exists():
                raise serializers.ValidationError("A product with this name already exists in your company.")
        return value

    def validate(self, data):
        """
        Custom validation for product data
        """
        # Validate selling price vs purchase price
        purchase_price = data.get('purchase_price', 0)
        selling_price = data.get('selling_price', 0)
        
        if selling_price < purchase_price:
            raise serializers.ValidationError({
                "selling_price": "Selling price cannot be less than purchase price"
            })
        
        # Validate stock quantities
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
        
        return data

    def create(self, validated_data):
        """
        Create product with automatic SKU generation and company assignment
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        # Set company from user
        company = getattr(request.user, 'company', None)
        if not company:
            raise serializers.ValidationError("User must be associated with a company")
        validated_data['company'] = company

        # Set created_by
        validated_data['created_by'] = request.user

        # Generate SKU
        if not validated_data.get('sku'):
            try:
                next_num = CompanyProductSequence.get_next_sequence(company)
                validated_data['sku'] = f"PDT-{company.id}-{next_num:05d}"
            except Exception as e:
                # Fallback SKU generation
                timestamp = int(time.time())
                random_suffix = random.randint(100, 999)
                validated_data['sku'] = f"PDT-{company.id}-{timestamp}{random_suffix}"

        # Save with retry logic for IntegrityError
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    product = Product.objects.create(**validated_data)
                return product
            except IntegrityError as e:
                if 'sku' in str(e).lower() and attempt < max_retries - 1:
                    # Regenerate SKU and retry
                    timestamp = int(time.time())
                    random_suffix = random.randint(100, 999)
                    validated_data['sku'] = f"PDT-{company.id}-{timestamp}{random_suffix}"
                    continue
                else:
                    raise serializers.ValidationError({
                        'sku': f'Could not generate unique SKU after {max_retries} attempts. Please try again.'
                    })

class ProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'alert_quantity', 
            'description', 'image', 'is_active'
        ]
        # Don't include opening_stock in update as it should only be set once

    def validate_name(self, value):
        """Ensure product name is unique within company, excluding current instance"""
        request = self.context.get('request')
        instance = self.instance
        
        if request and hasattr(request, 'user') and hasattr(request.user, 'company'):
            if Product.objects.filter(
                company=request.user.company, 
                name=value
            ).exclude(id=instance.id).exists():
                raise serializers.ValidationError("A product with this name already exists in your company.")
        return value

    def validate(self, data):
        """
        Custom validation for product update data
        """
        purchase_price = data.get('purchase_price', self.instance.purchase_price)
        selling_price = data.get('selling_price', self.instance.selling_price)
        
        if selling_price < purchase_price:
            raise serializers.ValidationError({
                "selling_price": "Selling price cannot be less than purchase price"
            })
        
        alert_quantity = data.get('alert_quantity', self.instance.alert_quantity)
        if alert_quantity < 0:
            raise serializers.ValidationError({
                "alert_quantity": "Alert quantity cannot be negative"
            })
        
        return data


class ProductSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # Foreign key fields
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=True)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=True)
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all(), required=False, allow_null=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    source = serializers.PrimaryKeyRelatedField(queryset=Source.objects.all(), required=False, allow_null=True)
    
    # Read-only info fields
    category_info = serializers.SerializerMethodField(read_only=True)
    unit_info = serializers.SerializerMethodField(read_only=True)
    brand_info = serializers.SerializerMethodField(read_only=True)
    group_info = serializers.SerializerMethodField(read_only=True)
    source_info = serializers.SerializerMethodField(read_only=True)
    created_by_info = serializers.SerializerMethodField(read_only=True)
    stock_status = serializers.ReadOnlyField()
    stock_status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'company', 'created_by', 'name', 'sku', 
            'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock', 
            'stock_qty', 'alert_quantity', 'description', 'image',
            'is_active', 'created_at', 'updated_at',
            'category_info', 'unit_info', 'brand_info', 'group_info', 
            'source_info', 'created_by_info', 'stock_status', 'stock_status_display'
        ]
        read_only_fields = [
            'id', 'company', 'created_by', 'created_at', 'updated_at', 
            'sku', 'stock_status', 'stock_qty'
        ]

    def get_category_info(self, obj):
        if obj.category:
            return {'id': obj.category.id, 'name': obj.category.name}
        return None

    def get_unit_info(self, obj):
        if obj.unit:
            return {'id': obj.unit.id, 'name': obj.unit.name}
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
        """Get human-readable stock status"""
        status_map = {
            0: 'Out of Stock',
            1: 'Low Stock', 
            2: 'In Stock'
        }
        return status_map.get(obj.stock_status, 'Unknown')