from rest_framework import serializers
from .models import Company, User, StaffRole, Staff
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class CustomTokenObtainSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")

        refresh = RefreshToken.for_user(user)
        
        # Staff info if exists
        staff = None
        if hasattr(user, "staff"):
            staff = {
                "id": user.staff.id,
                "role": user.staff.role.name if user.staff.role else None,
                "status": user.staff.status,
                "is_main_user": user.staff.is_main_user,
            }

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "company": {
                    "id": user.company.id,
                    "name": user.company.name,
                    "phone": user.company.phone,
                } if user.company else None,
                "staff": staff
            }
        }
# -----------------------------
# Company Serializer
# -----------------------------
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'


# -----------------------------
# User Serializer
# -----------------------------
class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', write_only=True, required=False
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'company', 'company_id', 'is_active', 'is_staff']


# -----------------------------
# Staff Role Serializer
# -----------------------------
class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = '__all__'


# -----------------------------
# Staff Serializer
# -----------------------------
class StaffSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    role = StaffRoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=StaffRole.objects.all(), source='role', write_only=True, required=False
    )

    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'user_id', 'role', 'role_id', 'phone', 'designation', 
            'salary', 'commission', 'is_main_user', 'status', 'joining_date', 'address', 'created_at'
        ]
