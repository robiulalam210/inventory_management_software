from rest_framework import viewsets
from core.base_viewsets import BaseCompanyViewSet  # আপনার পূর্বের base viewset
from .models import Company, User, StaffRole, Staff
from .serializers import CompanySerializer, UserSerializer, StaffRoleSerializer, StaffSerializer

# accounts/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

# Import serializers here
from .serializers import CustomUserSerializer

class CustomLoginView(APIView):
    """
    Login API that returns access & refresh tokens + full user info
    """
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        # Authenticate user
        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # Serialize full user info
        user_data = CustomUserSerializer(user).data

        # Build response
        response_data = {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "company": {
                    "id": user.company.id if user.company else None,
                    "name": user.company.name if user.company else None,
                    "phone": user.company.phone if user.company else None
                },
                "staff": user_data.get("staff")  # nested staff info if exists
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(access)
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
# -----------------------------
# Company CRUD
# -----------------------------
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


# -----------------------------
# User CRUD
# -----------------------------
class UserViewSet(BaseCompanyViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


# -----------------------------
# Staff Role CRUD
# -----------------------------
class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer


# -----------------------------
# Staff CRUD
# -----------------------------
class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
