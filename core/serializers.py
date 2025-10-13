from rest_framework import serializers
from .models import Company, User, StaffRole, Staff

# -----------------------------
# Staff Serializer
# -----------------------------
class StaffSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'role_name', 'phone', 'designation', 'salary',
            'commission', 'is_main_user', 'status', 'joining_date', 'address', 'created_at'
        ]

    def get_user(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "email": obj.user.email,
                "role": obj.user.role
            }
        return None

# -----------------------------
# Company Serializer
# -----------------------------
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "address", "phone", "logo", "is_active"]

# -----------------------------
# Custom User Serializer
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
