from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Category, Unit, Product, Supplier, Purchase, Customer, Sale

# ----------------- User Serializers -----------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'role')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        return User.objects.create_user(**validated_data)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role')

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password]) 

# ----------------- Inventory Serializers -----------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    unit = UnitSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), source='unit', write_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'unit', 'category_id', 'unit_id', 'quantity', 'price', 'description']

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

# ----------------- Purchase Serializer -----------------
class PurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = '__all__'

    def update(self, instance, validated_data):
        # Prevent updates to purchases to maintain stock integrity
        raise serializers.ValidationError("Updating purchases is not allowed.") 

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


class SaleSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source='customer.name')
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = Sale
        fields = '__all__'

    def create(self, validated_data):
        product = validated_data['product']
        quantity = validated_data['quantity']

        # 🔽 Stock check and auto decrease
        if product.stock < quantity:
            raise serializers.ValidationError("Not enough stock available!")

        product.stock -= quantity
        product.save()

        # Total auto calculate
        validated_data['total'] = quantity * product.price
        return super().create(validated_data)