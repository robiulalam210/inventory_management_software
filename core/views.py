from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.utils import timezone
from django.db import models

from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

import logging
logger = logging.getLogger(__name__)

from django.contrib.auth import get_user_model
User = get_user_model()

from .models import Company, StaffRole, Staff
from .serializers import (
    CompanySerializer,
    UserSerializer,
    StaffRoleSerializer,
    StaffSerializer,
    UserProfileSerializer,
    StaffProfileSerializer,
    CustomTokenObtainPairSerializer
)
from .utils import custom_response

# Import forms safely
try:
    from .forms import CompanyAdminSignupForm, UserForm, UserCreationForm
except ImportError:
    CompanyAdminSignupForm = None
    UserForm = None
    UserCreationForm = None

# --------------------------
# JWT / Login Views
# --------------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CustomLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username_or_email = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")

        if not username_or_email or not password:
            return Response({"error": "Username/Email and password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Find user by username or email
        try:
            user_obj = User.objects.get(
                Q(username=username_or_email) | Q(email=username_or_email)
            )
            final_username = user_obj.username
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Authenticate
        user = authenticate(username=final_username, password=password)
        if user is None:
            return Response({"error": "Invalid credentials"},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        serializer = CustomTokenObtainPairSerializer()
        refresh = serializer.get_token(user)
        access_token = refresh.access_token

        refresh["company_id"] = user.company.id if getattr(user, "company", None) else None
        refresh["company_name"] = user.company.name if getattr(user, "company", None) else None

        response_data = {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": getattr(user, 'role', None),
                "company_id": getattr(user.company, "id", None),
                "company_name": getattr(user.company, "name", None),
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(access_token),
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

# --------------------------
# Base ViewSets
# --------------------------
class BaseCompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if user.role == User.Role.SUPER_ADMIN:
            return queryset
        model = getattr(queryset, 'model', None)
        if model and hasattr(model, "company") and user.company:
            return queryset.filter(company=user.company)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        model = getattr(serializer.Meta, "model", None)
        if model and hasattr(model, "company") and user.company:
            serializer.save(company=user.company)
        else:
            serializer.save()

# --------------------------
# Company / User ViewSets
# --------------------------
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return Company.objects.all()
        if hasattr(user, 'company') and user.company:
            return Company.objects.filter(id=user.company.id)
        return Company.objects.none()

class UserViewSet(BaseCompanyViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            queryset = queryset.filter(id=user.id)
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page is not None else queryset, many=True)
            return custom_response(True, "Users fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Error fetching users: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(True, "User details fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Error fetching user details: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = request.user
            if hasattr(user, 'company') and user.company:
                serializer.save(company=user.company)
            else:
                serializer.save()
            return custom_response(True, "User created successfully.", serializer.data, status.HTTP_201_CREATED)
        except Exception as e:
            return custom_response(False, f"User creation failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------
# Staff Role / Staff
# --------------------------
class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer
    permission_classes = [IsAuthenticated]

class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer

# --------------------------
# Change Password
# --------------------------
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            current_password = request.data.get('current_password')
            new_password = request.data.get('new_password')

            if not current_password or not new_password:
                return custom_response(False, "Current password and new password are required", None, status.HTTP_400_BAD_REQUEST)

            if not user.check_password(current_password):
                return custom_response(False, "Current password is incorrect", None, status.HTTP_400_BAD_REQUEST)

            if len(new_password) < 8:
                return custom_response(False, "New password must be at least 8 characters long", None, status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()
            logger.info(f"Password changed for user: {user.username}")

            return custom_response(True, "Password changed successfully", None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}", exc_info=True)
            return custom_response(False, "Password change failed", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------
# Profile API
# --------------------------
class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            has_staff_profile = hasattr(user, 'staff_profile')

            profile_data = {
                'user': UserProfileSerializer(user).data,
                'staff_profile': StaffProfileSerializer(user.staff_profile).data if has_staff_profile else None,
                'permissions': user.get_permissions(),
                'company_info': CompanySerializer(user.company).data if hasattr(user, "company") and user.company else None
            }

            logger.info(f"User profile fetched for: {user.username}")
            return custom_response(True, "User profile fetched successfully", profile_data, status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
            return custom_response(False, "Error fetching user profile", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            user = request.user
            data = request.data.copy()
            sensitive_fields = ['password', 'is_superuser', 'is_staff', 'role', 'company', 'username']
            for field in sensitive_fields:
                data.pop(field, None)

            serializer = UserProfileSerializer(user, data=data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                has_staff_profile = hasattr(user, 'staff_profile')
                updated_profile_data = {
                    'user': UserProfileSerializer(user).data,
                    'staff_profile': StaffProfileSerializer(user.staff_profile).data if has_staff_profile else None,
                    'permissions': user.get_permissions(),
                    'company_info': {
                        'id': user.company.id if user.company else None,
                        'name': user.company.name if user.company else None,
                        'plan_type': user.company.plan_type if user.company else None,
                        'is_active': user.company.is_active if user.company else None,
                    } if hasattr(user, "company") and user.company else None
                }
                return custom_response(True, "Profile updated successfully", updated_profile_data, status.HTTP_200_OK)
            else:
                return custom_response(False, "Validation error", serializer.errors, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}", exc_info=True)
            return custom_response(False, "Error updating profile", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------
# User Permissions
# --------------------------
class UserPermissionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            permissions_data = {
                'role': user.role,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'permissions': user.get_permissions(),
                'can_manage_company': user.role in [user.Role.SUPER_ADMIN, user.Role.ADMIN],
            }
            return custom_response(True, "User permissions fetched successfully", permissions_data, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching user permissions: {str(e)}")
            return custom_response(False, "Error fetching permissions", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------
# Dashboard Stats
# --------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard_stats(request):
    try:
        user = request.user
        company = getattr(user, "company", None)
        if not company:
            return custom_response(False, "User has no company assigned", None, status.HTTP_400_BAD_REQUEST)

        from sales.models import Sale
        from purchases.models import Purchase
        from products.models import Product
        from customers.models import Customer
        from suppliers.models import Supplier

        stats = {
            'today_sales': Sale.objects.filter(company=company, sale_date__date=timezone.now().date()).aggregate(total=Sum('grand_total'))['total'] or 0,
            'today_orders': Sale.objects.filter(company=company, sale_date__date=timezone.now().date()).count(),
            'total_products': Product.objects.filter(company=company, is_active=True).count(),
            'total_customers': Customer.objects.filter(company=company, is_active=True).count(),
            'total_suppliers': Supplier.objects.filter(company=company, is_active=True).count(),
            'pending_purchases': Purchase.objects.filter(company=company, status='pending').count(),
            'due_sales': Sale.objects.filter(company=company, due_amount__gt=0).aggregate(total_due=Sum('due_amount'))['total_due'] or 0,
        }

        for key, value in stats.items():
            if hasattr(value, '__float__'):
                stats[key] = float(value)

        return custom_response(True, "Dashboard stats fetched successfully", stats, status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}", exc_info=True)
        return custom_response(False, "Error fetching dashboard statistics", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

# --------------------------
# Admin Web Views
# --------------------------
def company_admin_signup(request):
    if CompanyAdminSignupForm is None:
        return render(request, 'error.html', {'error': 'Forms module not available'})
    if request.method == 'POST':
        form = CompanyAdminSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
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
        if user is not None:
            if user.is_active:
                if user.is_staff or user.role in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
                    login(request, user)
                    return redirect('admin_dashboard')
                else:
                    return render(request, 'admin_login.html', {'error': 'This account does not have admin privileges.'})
            else:
                return render(request, 'admin_login.html', {'error': 'Account is inactive.'})
        else:
            return render(request, 'admin_login.html', {'error': 'Invalid username or password.'})
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
    if UserForm is None:
        return render(request, 'error.html', {'error': 'Forms module not available'})
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.company = request.user.company
            user.is_staff = user.role in [User.Role.ADMIN, User.Role.MANAGER]
            user.save()
            return redirect('user_list')
    else:
        form = UserForm()
    return render(request, 'create_user.html', {'form': form})

def user_management(request):
    if UserCreationForm is None:
        return render(request, 'error.html', {'error': 'Forms module not available'})
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
