# products/serializers.py
from rest_framework import serializers
from .models import Category, Unit, Brand, Group, Source, Product

# Category
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

# Unit
class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'

# Brand
class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

# Group
class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'

# Source
class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = '__all__'

# Product
class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    unit = UnitSerializer()
    brand = BrandSerializer()
    group = GroupSerializer()
    source = SourceSerializer()

    class Meta:
        model = Product
        fields = '__all__'
