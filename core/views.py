from rest_framework import viewsets
from core.base_viewsets import BaseCompanyViewSet  # আপনার পূর্বের base viewset
from .models import Company, User, StaffRole, Staff
from .serializers import CompanySerializer, UserSerializer, StaffRoleSerializer, StaffSerializer

# accounts/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomTokenObtainSerializer
class CustomLoginView(APIView):
    def post(self, request):
        serializer = CustomTokenObtainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
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
