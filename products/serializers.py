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

class ProductSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # Make foreign key fields optional and allow null
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        required=True  # Changed to required=True since it's mandatory
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(), 
        required=True  # Changed to required=True since it's mandatory
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
    
    # Read-only info fields
    category_info = serializers.SerializerMethodField(read_only=True)
    unit_info = serializers.SerializerMethodField(read_only=True)
    brand_info = serializers.SerializerMethodField(read_only=True)
    group_info = serializers.SerializerMethodField(read_only=True)
    source_info = serializers.SerializerMethodField(read_only=True)
    created_by_info = serializers.SerializerMethodField(read_only=True)
    
    stock_status = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'company', 'created_by', 'name', 'sku', 
            'category', 'unit', 'brand', 'group', 'source',
            'purchase_price', 'selling_price', 'opening_stock', 
            'stock_qty', 'alert_quantity', 'description', 'image',
            'is_active', 'created_at', 'updated_at',
            'category_info', 'unit_info', 'brand_info', 'group_info', 
            'source_info', 'created_by_info', 'stock_status'
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at', 'updated_at', 'sku', 'stock_status']

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
            return {'id': obj.created_by.id, 'username': obj.created_by.username}
        return None

    def validate(self, data):
        """
        Custom validation for product data
        """
        # Validate required fields
        if not data.get('category'):
            raise serializers.ValidationError({"category": "Category is required"})
        
        if not data.get('unit'):
            raise serializers.ValidationError({"unit": "Unit is required"})
        
        if not data.get('name'):
            raise serializers.ValidationError({"name": "Product name is required"})

        # Ensure selling price is not less than purchase price
        purchase_price = data.get('purchase_price', 0)
        selling_price = data.get('selling_price', 0)
        
        try:
            if selling_price < purchase_price:
                raise serializers.ValidationError({
                    "selling_price": "Selling price cannot be less than purchase price"
                })
        except TypeError:
            # If values are not comparable, let field validation handle it
            pass
        
        # Ensure stock quantities are valid
        opening_stock = data.get('opening_stock', 0)
        if opening_stock is not None and opening_stock < 0:
            raise serializers.ValidationError({
                "opening_stock": "Opening stock cannot be negative"
            })
        
        alert_quantity = data.get('alert_quantity', 5)
        if alert_quantity is not None and alert_quantity < 0:
            raise serializers.ValidationError({
                "alert_quantity": "Alert quantity cannot be negative"
            })
        
        return data

    def _generate_fallback_sku(self, company):
        """Generate a fallback SKU using timestamp and random number"""
        timestamp = int(time.time())
        random_suffix = random.randint(100, 999)
        company_id = company.id if company else "0"
        return f"PDT-{company_id}-{timestamp}{random_suffix}"

    def create(self, validated_data):
        """
        Create product with automatic SKU generation
        """
        request = self.context.get('request', None)
        user = getattr(request, 'user', None)

        # Ensure company is set
        company = validated_data.get('company', None)
        if company is None:
            company = getattr(user, 'company', None) or getattr(getattr(user, 'profile', None), 'company', None)
            if company is None:
                raise serializers.ValidationError({'company': 'Company is required.'})
            validated_data['company'] = company

        # Set created_by if possible
        if 'created_by' not in validated_data or validated_data.get('created_by') is None:
            if user and getattr(user, 'is_authenticated', False):
                validated_data['created_by'] = user

        # Set initial stock
        if 'stock_qty' not in validated_data:
            validated_data['stock_qty'] = validated_data.get('opening_stock', 0)

        # SKU generation if not provided
        if not validated_data.get('sku'):
            # Use CompanyProductSequence if available
            if CompanyProductSequence is not None:
                try:
                    # FIX: Use the correct method name get_next_sequence instead of next_for_company
                    next_num = CompanyProductSequence.get_next_sequence(company)
                    validated_data['sku'] = f"PDT-{company.id}-{next_num}"
                except Exception as e:
                    # Fallback if sequence fails
                    validated_data['sku'] = self._generate_fallback_sku(company)
            else:
                # Fallback SKU generation
                validated_data['sku'] = self._generate_fallback_sku(company)

        # Save with retry logic for IntegrityError (SKU conflicts)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    product = super().create(validated_data)
                return product
            except IntegrityError as e:
                if 'sku' in str(e).lower() and attempt < max_retries - 1:
                    # Regenerate SKU and retry
                    validated_data['sku'] = self._generate_fallback_sku(company)
                    continue
                else:
                    # Re-raise the exception if we've exhausted retries
                    raise serializers.ValidationError({
                        'sku': f'Could not generate unique SKU after {max_retries} attempts. Please try again.'
                    })

    def update(self, instance, validated_data):
        """
        Ensure we don't accidentally overwrite read-only fields
        """
        # Remove read-only fields
        for read_only in ('company', 'created_by', 'sku', 'id', 'created_at', 'updated_at'):
            validated_data.pop(read_only, None)

        return super().update(instance, validated_data)