from rest_framework import serializers
from .models import Company, User, StaffRole, Staff
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers as drf_serializers
# Custom Token Serializer (TokenObtainPair)
# -----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Custom claims
        token["username"] = user.username
        token["role"] = getattr(user, "role", None)
        token["user_id"] = user.id

        # Company fields
        if hasattr(user, "company") and user.company:
            token["company_id"] = user.company.id
            token["company_name"] = user.company.name
        else:
            token["company_id"] = None
            token["company_name"] = None
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Check company license
        if hasattr(user, "company") and user.company and not user.company.is_active:
            raise serializers.ValidationError("Company license expired. Please contact support.")

        # Extra data returned in login response
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": getattr(user, "role", None),
            "company_id": user.company.id if hasattr(user, "company") and user.company else None,
            "company_name": user.company.name if hasattr(user, "company") and user.company else None,
        }

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id", "name", "company_code", "address", "phone", "email", 
            "logo", "is_active", "plan_type", "start_date", "expiry_date",
            "days_until_expiry", "active_user_count", "product_count"
        ]
        read_only_fields = ["company_code", "days_until_expiry", "active_user_count", "product_count"]


class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = "__all__"


class StaffSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    user_info = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "id", "user_info", "role", "role_name", "phone", "designation", 
            "employment_type", "salary", "commission", "bonus", "total_compensation",
            "is_main_user", "status", "joining_date", "employment_duration",
            "address", "created_at"
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
            }
        return None


class CustomUserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    staff_profile = StaffSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "role", 
            "company", "phone", "is_active", "is_staff", "is_verified",
            "last_login", "date_joined", "staff_profile"
        ]


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source="company", write_only=True, required=False
    )
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password", "first_name", "last_name",
            "role", "company", "company_id", "phone", "is_active", "is_staff"
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
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