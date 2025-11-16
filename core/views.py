from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from rest_framework.permissions import AllowAny  # Add this import

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Company, User, StaffRole, Staff
from .serializers import (
    CompanySerializer,
    UserSerializer,
    StaffRoleSerializer,
    StaffSerializer,
    CustomUserSerializer,
    CustomTokenObtainPairSerializer
)
from .utils import custom_response

# Fix: Import forms correctly
try:
    from .forms import CompanyAdminSignupForm, UserForm, UserCreationForm
except ImportError:
    # Fallback if forms don't exist yet
    CompanyAdminSignupForm = None
    UserForm = None
    UserCreationForm = None


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CustomLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if user is None:
            return Response({"error": "Invalid credentials"},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Use your custom token serializer
        serializer = CustomTokenObtainPairSerializer()

        refresh = serializer.get_token(user)
        access_token = refresh.access_token

        # Ensure company info is inside the token
        refresh["company_id"] = user.company.id if user.company else None
        refresh["company_name"] = user.company.name if user.company else None

        response_data = {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": getattr(user, 'role', None),
                "company_id": user.company.id if user.company else None,
                "company_name": user.company.name if user.company else None,
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(access_token),
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    
class TestView(APIView):
    """
    Test view to verify URL routing
    """
    def get(self, request):
        return Response({
            "message": "✅ Test endpoint is working!",
            "endpoints": {
                "api_login": "POST /api/auth/login/",
                "api_test": "GET /api/test/",
                "admin_login": "GET /admin/login/",
                "django_admin": "GET /admin/"
            }
        })


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


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.SUPER_ADMIN:
            return Company.objects.all()
        if user.company:
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = request.user
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
        except Exception as e:
            return custom_response(
                success=False,
                message="User creation failed: " + str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer
    permission_classes = [IsAuthenticated]


class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer


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
                    return render(request, 'admin_login.html', {
                        'error': 'This account does not have admin privileges.'
                    })
            else:
                return render(request, 'admin_login.html', {
                    'error': 'Account is inactive.'
                })
        else:
            return render(request, 'admin_login.html', {
                'error': 'Invalid username or password.'
            })
    
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
            
            if user.role in [User.Role.ADMIN, User.Role.MANAGER]:
                user.is_staff = True
            else:
                user.is_staff = False
                
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