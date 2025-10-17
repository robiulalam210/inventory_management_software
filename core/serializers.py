from rest_framework import serializers
from .models import Company, User, StaffRole, Staff
# auth/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role
        token["company_id"] = user.company.id if user.company else None
        token["company_name"] = user.company.name if user.company else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Check if company is expired
        if user.company and not user.company.is_active:
            raise serializers.ValidationError("Company license expired. Please contact support.")
        
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "company_id": user.company.id if user.company else None,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# -----------------------------
# Company Serializer
# -----------------------------
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "address", "phone", "logo", "is_active", "start_date", "expiry_date"]


# -----------------------------
# Staff Role Serializer
# -----------------------------
class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = "__all__"


# -----------------------------
# Staff Serializer
# -----------------------------
class StaffSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "id", "user", "role_name", "phone", "designation", "salary",
            "commission", "is_main_user", "status", "joining_date", "address", "created_at"
        ]

    def get_user(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "email": obj.user.email,
                "role": obj.user.role,
            }
        return None


# -----------------------------
# Custom User Serializer (for token)
# -----------------------------
class CustomUserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    staff = StaffSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "company", "staff"]


# -----------------------------
# User Serializer (CRUD)
# -----------------------------
class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source="company", write_only=True, required=False
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "company", "company_id", "is_active", "is_staff"]
