from rest_framework import serializers
from .models import Category, Unit, Brand, Group, Source, Product

# ক্যাটাগরি সিরিয়ালাইজার (কোম্পানি read_only)
class CategorySerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Category
        fields = '__all__'

# ইউনিট সিরিয়ালাইজার
class UnitSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Unit
        fields = '__all__'

# ব্র্যান্ড সিরিয়ালাইজার
class BrandSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Brand
        fields = '__all__'

# গ্রুপ সিরিয়ালাইজার
class GroupSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Group
        fields = '__all__'

# সোর্স সিরিয়ালাইজার
class SourceSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Source
        fields = '__all__'

# প্রোডাক্ট সিরিয়ালাইজার
class ProductSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)  # কোম্পানি read_only
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=True, allow_null=True)
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all(), required=False, allow_null=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    source = serializers.PrimaryKeyRelatedField(queryset=Source.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Product
        fields = '__all__'