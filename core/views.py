# apps/your_app/views.py
from datetime import timezone as _tz  # noqa: F401 - keep if later used
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers as drf_serializers

# Models & serializers
from .models import Company, User, StaffRole, Staff
from .serializers import (
    CompanySerializer,
    UserSerializer,
    StaffRoleSerializer,
    StaffSerializer,
    CustomUserSerializer,
)
from rest_framework import viewsets, status, serializers
from rest_framework.permissions import IsAuthenticated
from core.utils import custom_response
from .models import User
from .serializers import UserSerializer
from core.base_viewsets import BaseCompanyViewSet

# Forms (fix: froms -> forms). Ensure you have these forms implemented.
from .froms import CompanyAdminSignupForm, UserForm, UserCreationForm


# -----------------------------
# Custom Token Serializer (TokenObtainPair)
# -----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # embed useful claims
        token["username"] = user.username
        token["role"] = user.role
        token["user_id"] = user.id
        token["company_id"] = user.company.id if user.company else None
        token["company_name"] = user.company.name if user.company else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # company license check (if you want to block login for expired companies)
        if user.company and not user.company.is_active:
            raise drf_serializers.ValidationError("Company license expired. Please contact support.")

        # add user info to response
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "company_id": user.company.id if user.company else None,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# -----------------------------
# (Optional) Custom Login that returns Refresh + Access + user object
# -----------------------------
class CustomLoginView(APIView):
    """
    Optional: Use this if you prefer /api/login/ POST with username+password
    and get back refresh/access + user payload.
    Alternatively use CustomTokenObtainPairView at /api/token/.
    """
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # check company active
        if user.company and not user.company.is_active:
            return Response({"detail": "Company license expired."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        user_data = CustomUserSerializer(user).data

        return Response(
            {
                "user": user_data,
                "tokens": {"refresh": str(refresh), "access": str(access)},
            },
            status=status.HTTP_200_OK,
        )


# -----------------------------
# Base Company ViewSet (Auto Filter by Company)
# -----------------------------
class BaseCompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Super Admin sees all
        if user.role == User.Role.SUPER_ADMIN:
            return queryset

        # If model has company FK -> filter by user's company
        model = getattr(queryset, 'model', None)
        if model and hasattr(model, "company") and user.company:
            return queryset.filter(company=user.company)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        model = getattr(serializer.Meta, "model", None)

        # Only assign company if user has one (not super admin creating company)
        if model and hasattr(model, "company") and user.company:
            serializer.save(company=user.company)
        else:
            serializer.save()



# -----------------------------
# Company CRUD
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # super admin sees all companies
        if user.role == User.Role.SUPER_ADMIN:
            return Company.objects.all()
        # regular users see only their company
        if user.company:
            return Company.objects.filter(id=user.company.id)
        return Company.objects.none()


# -----------------------------
# User CRUD
class UserViewSet(BaseCompanyViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    # -----------------------------
    # List Users
    # -----------------------------
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page is not None else queryset, many=True)
            return custom_response(
                success=True,
                message="Users fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message="Error fetching users: " + str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # -----------------------------
    # Retrieve a single User
    # -----------------------------
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="User details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message="Error fetching user details: " + str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # -----------------------------
    # Create User
    # -----------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = request.user
            # Assign company only if creator has a company
            if user.company:
                serializer.save(company=user.company)
            else:
                serializer.save()
            return custom_response(
                success=True,
                message="User created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message="User creation failed: " + str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# -----------------------------
# Staff Role CRUD
class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer
    permission_classes = [IsAuthenticated]


# -----------------------------
# Staff CRUD
class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer


# -----------------------------
# Django Admin UI Views (templates)
# -----------------------------
def company_admin_signup(request):
    if request.method == 'POST':
        form = CompanyAdminSignupForm(request.POST)
        if form.is_valid():
            # নতুন কোম্পানি শুধু Admin সাইনআপের সময় তৈরি হবে
            company = Company.objects.create(name=form.cleaned_data['company_name'])
            user = form.save(commit=False)
            user.role = User.Role.ADMIN
            user.company = company
            user.save()
            login(request, user)
            return redirect('admin_dashboard')
    else:
        form = CompanyAdminSignupForm()
    return render(request, 'admin_signup.html', {'form': form})


def company_admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and user.role == User.Role.ADMIN:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            return render(request, 'admin_login.html', {'error': 'Invalid credentials or not an admin.'})
    return render(request, 'admin_login.html')


@login_required
@user_passes_test(lambda u: u.role == User.Role.ADMIN)
def dashboard(request):
    return render(request, 'admin_dashboard.html')


@login_required
@user_passes_test(lambda u: u.role == User.Role.ADMIN)
def user_list(request):
    users = User.objects.filter(company=request.user.company).exclude(id=request.user.id)
    return render(request, 'user_list.html', {'users': users})


@login_required
@user_passes_test(lambda u: u.role == User.Role.ADMIN)
def create_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.company = request.user.company
            user.save()
            return redirect('user_list')
    else:
        form = UserForm()
    return render(request, 'create_user.html', {'form': form})


def user_management(request):
    users = User.objects.all()
    form = UserCreationForm()
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('user_management')
    return render(request, "user_management.html", {"users": users, "form": form})


def home(request):
    return render(request, "home.html")
