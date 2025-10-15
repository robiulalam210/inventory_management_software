from rest_framework import viewsets
from core.base_viewsets import BaseCompanyViewSet
from .models import Company, User, StaffRole, Staff
from .serializers import CompanySerializer, UserSerializer, StaffRoleSerializer, StaffSerializer, CustomUserSerializer
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from .froms import CompanyAdminSignupForm, UserForm
from .froms import UserCreationForm
from .models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

# JWT login
class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token["username"] = user.username
        token["role"] = getattr(user, "role", None)
        token["email"] = getattr(user, "email", None)
        token["company_id"] = getattr(user.company, "id", None) if user.company else None
        return token

class CustomLoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = CustomRefreshToken.for_user(user)
        access = refresh.access_token
        user_data = CustomUserSerializer(user).data
        return Response({
            "user": user_data,
            "tokens": {"refresh": str(refresh), "access": str(access)}
        }, status=status.HTTP_200_OK)

# Company CRUD
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

# User CRUD
class UserViewSet(BaseCompanyViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Staff Role CRUD
class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer

# Staff CRUD
class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer

# Django Admin UI
def company_admin_signup(request):
    if request.method == 'POST':
        form = CompanyAdminSignupForm(request.POST)
        if form.is_valid():
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
            return redirect('user_management')  # or your url name
    return render(request, "user_management.html", {
        "users": users,
        "form": form
    })
def home(request):
    return render(request, "home.html")