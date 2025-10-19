from rest_framework import serializers
from django.conf import settings
from django.db import transaction, IntegrityError
from .models import Category, Unit, Brand, Group, Source, Product

# Try to import CompanyProductSequence if you implemented it in models.py.
# If it's not present we will fallback to a best-effort generation approach.
try:
    from .models import CompanyProductSequence  # type: ignore
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
        required=False, 
        allow_null=True
    )
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.all(), 
        required=False, 
        allow_null=True
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
        # Ensure selling price is not less than purchase price
        purchase_price = data.get('purchase_price', 0)
        selling_price = data.get('selling_price', 0)
        
        # purchase_price / selling_price are Decimal fields after validation; handle safely
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

    def create(self, validated_data):
        """
        Ensure company and created_by are set from request (if available) and
        generate a per-company SKU if not provided.

        This implementation:
        - Reads request from serializer context and extracts user and company.
        - Prefers a CompanyProductSequence (if implemented) for concurrency-safe sequence.
        - Falls back to a best-effort generation with retries on IntegrityError.
        """
        request = self.context.get('request', None)
        user = getattr(request, 'user', None)

        # Ensure company is set: prefer validated_data, else try to take from user/profile
        company = validated_data.get('company', None)
        if company is None:
            # Common patterns: user.company or user.profile.company
            company = getattr(user, 'company', None) or getattr(getattr(user, 'profile', None), 'company', None)
            if company is None:
                raise serializers.ValidationError({'company': 'Company is required.'})
            validated_data['company'] = company

        # Set created_by if possible
        if 'created_by' not in validated_data or validated_data.get('created_by') is None:
            if user and getattr(user, 'is_authenticated', False):
                validated_data['created_by'] = user

        # Ensure opening_stock and stock_qty consistency on create if not provided
        if 'opening_stock' not in validated_data:
            validated_data['opening_stock'] = 0
        if 'stock_qty' not in validated_data:
            # default behaviour: set stock_qty = opening_stock
            validated_data['stock_qty'] = validated_data.get('opening_stock', 0)

        # SKU generation if not provided
        if not validated_data.get('sku'):
            prefix = "PDT-"

            # 1) Prefer using CompanyProductSequence if available (recommended)
            if CompanyProductSequence is not None:
                # next_for_company handles transaction + locking at model level
                next_num = CompanyProductSequence.next_for_company(company)
                validated_data['sku'] = f"{prefix}{next_num:04d}"
                # create inside a transaction for safety
                with transaction.atomic():
                    product = super().create(validated_data)
                return product

            # 2) Fallback approach: compute next numeric suffix for this company and prefix.
            # This is not fully safe under high concurrency. We will attempt a few retries if IntegrityError occurs.
            def _next_candidate():
                max_num = 0
                qs = Product.objects.filter(company=company, sku__startswith=prefix).values_list('sku', flat=True)
                for s in qs:
                    try:
                        n = int(s.replace(prefix, ''))
                        if n > max_num:
                            max_num = n
                    except Exception:
                        continue
                return max_num + 1

            attempts = 0
            max_attempts = 5
            while attempts < max_attempts:
                candidate_num = _next_candidate()
                candidate_sku = f"{prefix}{candidate_num:04d}"
                validated_data['sku'] = candidate_sku
                try:
                    with transaction.atomic():
                        product = super().create(validated_data)
                    return product
                except IntegrityError:
                    # possible race condition: another process created same SKU concurrently
                    attempts += 1
                    # retry with a newly computed candidate
                    continue

            # If we reach here, retries failed
            raise serializers.ValidationError({'sku': 'Could not generate a unique SKU. Please try again.'})
        else:
            # SKU was provided by client: simply create (let DB raise IntegrityError if duplicate)
            with transaction.atomic():
                product = super().create(validated_data)
            return product

    def update(self, instance, validated_data):
        """
        Ensure we don't accidentally overwrite read-only fields like company/created_by/sku.
        For safety, pop read-only keys if they exist in validated_data.
        """
        for read_only in ('company', 'created_by', 'sku', 'id', 'created_at', 'updated_at'):
            validated_data.pop(read_only, None)

        # If opening_stock provided and you want to adjust stock_qty accordingly on update,
        # implement that logic here. For now we keep existing stock_qty unless explicitly provided.
        return super().update(instance, validated_data)