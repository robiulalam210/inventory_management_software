from rest_framework import serializers
from .models import Company, User, StaffRole, Staff, RolePermission
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


# -----------------------------
# Custom Token Serializer
# -----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        
        # Check company license
        if hasattr(user, "company") and user.company and not user.company.is_active:
            raise serializers.ValidationError("Company license expired. Please contact support.")
        
        # Get user permissions
        permissions = user.get_permissions()
        
        # Extra data returned in login response
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "company_id": user.company.id if hasattr(user, "company") and user.company else None,
            "company_name": user.company.name if hasattr(user, "company") and user.company else None,
            "permissions": permissions
        }
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Custom claims
        token["username"] = user.username
        token["role"] = user.role
        token["user_id"] = user.id

        # Company fields
        if hasattr(user, "company") and user.company:
            token["company_id"] = user.company.id
            token["company_name"] = user.company.name
        else:
            token["company_id"] = None
            token["company_name"] = None
        
        return token


# -----------------------------
# Company Serializers
# -----------------------------
class CompanySerializer(serializers.ModelSerializer):
    active_user_count = serializers.IntegerField(read_only=True)
    product_count = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'trade_license', 'address', 'phone', 'email',
            'website', 'logo', 'currency', 'timezone', 'fiscal_year_start',
            'plan_type', 'start_date', 'expiry_date', 'is_active',
            'max_users', 'max_products', 'max_branches', 'company_code',
            'active_user_count', 'product_count', 'is_expired', 'days_until_expiry',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['company_code', 'created_at', 'updated_at']


# -----------------------------
# User Serializers
# -----------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    company_info = CompanySerializer(source='company', read_only=True)
    full_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'company', 'company_info', 'phone', 'profile_picture',
            'date_of_birth', 'is_verified', 'last_login', 'date_joined',
            'permissions', 'is_active', 'is_staff', 'is_superuser'
        ]
        read_only_fields = [
            'id', 'is_verified', 'last_login', 'date_joined', 
            'permissions', 'is_active', 'is_staff', 'is_superuser'
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_permissions(self, obj):
        return obj.get_permissions()


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), 
        source="company", 
        write_only=True, 
        required=False,
        allow_null=True
    )
    password = serializers.CharField(write_only=True, required=False)
    full_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password", "first_name", "last_name", "full_name",
            "role", "company", "company_id", "phone", "is_active", "is_staff", "is_superuser",
            "is_verified", "permissions", "date_joined", "last_login"
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'role': {'required': True}
        }

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_permissions(self, obj):
        return obj.get_permissions()

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        
        # Set default role if not provided
        if 'role' not in validated_data:
            validated_data['role'] = User.Role.STAFF
        
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
        else:
            # Set default password
            user.set_password('password123')
        
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password", "first_name", "last_name",
            "role", "company", "phone", "is_active"
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'required': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


# -----------------------------
# Staff Role Serializers
# -----------------------------
class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = ['id', 'module', 'can_view', 'can_create', 'can_edit', 'can_delete', 'can_export']


class StaffRoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    permission_details = RolePermissionSerializer(source='permissions', many=True, read_only=True)
    
    class Meta:
        model = StaffRole
        fields = [
            'id', 'name', 'role_type', 'description', 'company',
            'default_permissions', 'permissions', 'permission_details',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_permissions(self, obj):
        return obj.get_permissions_dict()


class StaffRoleCreateUpdateSerializer(serializers.ModelSerializer):
    permissions = serializers.JSONField(write_only=True, required=False)
    
    class Meta:
        model = StaffRole
        fields = [
            'id', 'name', 'role_type', 'description', 'company',
            'permissions', 'is_active'
        ]

    def create(self, validated_data):
        permissions_data = validated_data.pop('permissions', None)
        instance = super().create(validated_data)
        
        if permissions_data:
            instance.update_permissions(permissions_data)
        
        return instance

    def update(self, instance, validated_data):
        permissions_data = validated_data.pop('permissions', None)
        instance = super().update(instance, validated_data)
        
        if permissions_data is not None:
            instance.update_permissions(permissions_data)
        
        return instance


# -----------------------------
# Staff Serializers
# -----------------------------
class StaffProfileSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    role_info = StaffRoleSerializer(source='role', read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)
    employment_duration = serializers.IntegerField(read_only=True)
    total_compensation = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'user_info', 'company', 'role', 'role_info',
            'phone', 'alternate_phone', 'image', 'designation',
            'employment_type', 'employee_id', 'department',
            'salary', 'commission', 'bonus', 'total_compensation',
            'is_main_user', 'status', 'joining_date', 'leaving_date', 'contract_end_date',
            'address', 'emergency_contact', 'emergency_phone',
            'is_currently_active', 'employment_duration', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'employee_id', 'is_currently_active', 
            'employment_duration', 'total_compensation', 'created_at', 'updated_at'
        ]

    def get_user_info(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "email": obj.user.email,
                "first_name": obj.user.first_name,
                "last_name": obj.user.last_name,
                "role": obj.user.role,
                "full_name": obj.user.full_name,
            }
        return None


class StaffSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_type = serializers.CharField(source='role.role_type', read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)
    total_compensation = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Staff
        fields = [
            "id", "user", "user_info", "company", "role", "role_name", "role_type",
            "phone", "designation", "employment_type", "employee_id", "department",
            "salary", "commission", "bonus", "total_compensation",
            "is_main_user", "status", "joining_date", "employment_duration",
            "is_currently_active", "created_at", "updated_at"
        ]

    def get_user_info(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "email": obj.user.email,
                "first_name": obj.user.first_name,
                "last_name": obj.user.last_name,
                "role": obj.user.role,
                "full_name": obj.user.full_name,
                "is_active": obj.user.is_active,
            }
        return None


# -----------------------------
# Login Serializer
# -----------------------------
class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        email = attrs.get('email')
        password = attrs.get('password')

        if not (username or email):
            raise serializers.ValidationError('Must include "username" or "email"')
        
        if not password:
            raise serializers.ValidationError('Must include "password"')

        # Authenticate user
        if email:
            try:
                user_obj = User.objects.get(email=email)
                username = user_obj.username
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
        
        user = authenticate(username=username, password=password)
        
        if not user:
            raise serializers.ValidationError('Invalid credentials')
            
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        
        attrs['user'] = user
        return attrs