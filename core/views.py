from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.utils import timezone
from django.db import models

from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404

import logging
logger = logging.getLogger(__name__)

from django.contrib.auth import get_user_model
User = get_user_model()

# সংশোধিত import - RolePermission রিমুভ করা হয়েছে
from .models import Company, StaffRole, Staff, UserPermission
from .serializers import (
    CompanySerializer,
    UserSerializer,
    UserCreateSerializer,
    StaffRoleSerializer,
    StaffRoleCreateUpdateSerializer,
    StaffSerializer,
    StaffProfileSerializer,
    UserProfileSerializer,
    CustomTokenObtainPairSerializer,
    UserLoginSerializer,
    UserPermissionUpdateSerializer,
    UserPermissionResetSerializer,
    UserListSerializer,
    PermissionCheckSerializer,
    UserPermissionSerializer
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
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']

            # JWT tokens
            token_serializer = CustomTokenObtainPairSerializer()
            refresh = token_serializer.get_token(user)

            # Permissions
            permissions = user.get_permissions()

            # Company data
            company_data = (
                CompanySerializer(user.company).data
                if getattr(user, "company", None)
                else None
            )

            response_data = {
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "full_name": user.full_name,
                        "role": user.role,
                        "permission_source": user.permission_source,
                        "is_staff": user.is_staff,
                        "is_superuser": user.is_superuser,
                        "permissions": permissions,
                    },
                    "company": company_data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
            }

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(
            {
                "success": False,
                "message": "Login failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )


# --------------------------
# Base ViewSets
# --------------------------
class BaseCompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Super admin can see all
        if user.role == User.Role.SUPER_ADMIN:
            return queryset
        
        # For other users, filter by company
        model = getattr(queryset, 'model', None)
        if model and hasattr(model, "company") and user.company:
            return queryset.filter(company=user.company)
        
        # If model has user field, filter by user
        if model and hasattr(model, "user"):
            return queryset.filter(user=user)
        
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        model = getattr(serializer.Meta, "model", None)
        
        if model and hasattr(model, "company") and user.company:
            serializer.save(company=user.company)
        elif model and hasattr(model, "user"):
            serializer.save(user=user)
        else:
            serializer.save()


# --------------------------
# Company ViewSet
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

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.SUPER_ADMIN:
            return custom_response(
                False, 
                "Only super admin can create companies", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        return super().create(request, *args, **kwargs)


# --------------------------
# User ViewSet
# --------------------------
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.Role.SUPER_ADMIN:
            return User.objects.all()
        elif user.role == User.Role.ADMIN:
            if user.company:
                return User.objects.filter(company=user.company)
            else:
                return User.objects.filter(id=user.id)
        else:
            # Regular users can only see their own profile
            return User.objects.filter(id=user.id)

    def list(self, request, *args, **kwargs):
        """Override list to enforce permission"""
        user = request.user

        # STAFF or anyone without 'view' permission cannot see the list
        if not user.has_permission('users', 'view'):
            return custom_response(
                False,
                "You don't have permission to view users",
                None,
                status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return custom_response(
            True,
            "Users fetched successfully",
            serializer.data,
            status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        user = request.user
        if not user.has_permission('users', 'create'):
            return custom_response(
                False, 
                "You don't have permission to create users", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        if user.role != User.Role.SUPER_ADMIN and user.company:
            request.data['company'] = user.company.id
        
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return custom_response(
                True, 
                "User created successfully", 
                serializer.data, 
                status.HTTP_201_CREATED
            )
        except Exception as e:
            return custom_response(
                False, 
                f"User creation failed: {str(e)}", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        user = request.user
        if not user.has_permission('users', 'edit'):
            return custom_response(
                False, 
                "You don't have permission to edit users", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        if not user.has_permission('users', 'delete'):
            return custom_response(
                False, 
                "You don't have permission to delete users", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        instance = self.get_object()
        if instance.id == request.user.id:
            return custom_response(
                False, 
                "You cannot delete your own account", 
                None, 
                status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user = self.get_object()
        request_user = request.user
        
        if not request_user.has_permission('users', 'edit'):
            return custom_response(
                False, 
                "You don't have permission to assign roles", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        role_id = request.data.get('role_id')
        if not role_id:
            return custom_response(
                False, 
                "Role ID is required", 
                None, 
                status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = StaffRole.objects.get(id=role_id, company=request_user.company)
            
            staff_profile, created = Staff.objects.get_or_create(
                user=user,
                defaults={'company': request_user.company}
            )
            
            staff_profile.role = role
            staff_profile.save()
            
            user.assign_role_permissions(role)
            
            return custom_response(
                True, 
                "Role assigned successfully", 
                UserSerializer(user).data, 
                status.HTTP_200_OK
            )
            
        except StaffRole.DoesNotExist:
            return custom_response(
                False, 
                "Role not found", 
                None, 
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error assigning role: {str(e)}")
            return custom_response(
                False, 
                f"Error: {str(e)}", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# --------------------------
# User Permission Management Views
# --------------------------
class UserPermissionManagementView(APIView):
    """View for managing user permissions (Admin only)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Update user permissions"""
        serializer = UserPermissionUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = serializer.save()
            return custom_response(
                True,
                "User permissions updated successfully",
                {
                    'user_id': user.id,
                    'username': user.username,
                    'permissions': user.get_permissions(),
                    'permission_source': user.permission_source
                },
                status.HTTP_200_OK
            )
        
        return custom_response(
            False,
            "Permission update failed",
            serializer.errors,
            status.HTTP_400_BAD_REQUEST
        )
    
    def delete(self, request):
        """Reset user permissions to role defaults"""
        serializer = UserPermissionResetSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = serializer.save()
            return custom_response(
                True,
                "User permissions reset to role defaults",
                {
                    'user_id': user.id,
                    'username': user.username,
                    'permissions': user.get_permissions(),
                    'permission_source': user.permission_source
                },
                status.HTTP_200_OK
            )
        
        return custom_response(
            False,
            "Permission reset failed",
            serializer.errors,
            status.HTTP_400_BAD_REQUEST
        )


class UserPermissionListView(APIView):
    """List all user permissions for a specific user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        try:
            target_user = User.objects.get(id=user_id)
            request_user = request.user
            
            # Check permissions
            if not request_user.can_manage_user(target_user):
                return custom_response(
                    False,
                    "You don't have permission to view this user's permissions",
                    None,
                    status.HTTP_403_FORBIDDEN
                )
            
            # Get all permissions
            permissions = target_user.get_permissions()
            custom_perms = UserPermission.objects.filter(user=target_user, is_active=True)
            
            return custom_response(
                True,
                "User permissions fetched successfully",
                {
                    'user': {
                        'id': target_user.id,
                        'username': target_user.username,
                        'full_name': target_user.full_name,
                        'role': target_user.role,
                        'permission_source': target_user.permission_source
                    },
                    'permissions': permissions,
                    'custom_permissions': UserPermissionSerializer(custom_perms, many=True).data
                },
                status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return custom_response(
                False,
                "User not found",
                None,
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching user permissions: {str(e)}")
            return custom_response(
                False,
                "Error fetching user permissions",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CompanyUsersView(APIView):
    """Get all users in a company (for admin dashboard)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role == User.Role.SUPER_ADMIN:
            users = User.objects.all()
        elif user.role == User.Role.ADMIN and user.company:
            users = User.objects.filter(company=user.company).exclude(role=User.Role.SUPER_ADMIN)
        else:
            return custom_response(
                False,
                "You don't have permission to view company users",
                None,
                status.HTTP_403_FORBIDDEN
            )
        
        serializer = UserListSerializer(users, many=True)
        
        return custom_response(
            True,
            "Company users fetched successfully",
            {
                'total_users': users.count(),
                'users': serializer.data
            },
            status.HTTP_200_OK
        )


class PermissionCheckView(APIView):
    """Check if user has specific permission"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PermissionCheckSerializer(data=request.data)
        
        if serializer.is_valid():
            module = serializer.validated_data['module']
            action = serializer.validated_data.get('action')
            
            has_perm = request.user.has_permission(module, action)
            
            return custom_response(
                True,
                "Permission check completed",
                {
                    'has_permission': has_perm,
                    'module': module,
                    'action': action
                },
                status.HTTP_200_OK
            )
        
        return custom_response(
            False,
            "Invalid request data",
            serializer.errors,
            status.HTTP_400_BAD_REQUEST
        )


# --------------------------
# Staff Role ViewSet
# --------------------------
class StaffRoleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.Role.SUPER_ADMIN:
            return StaffRole.objects.all()
        
        if user.company:
            return StaffRole.objects.filter(company=user.company)
        
        return StaffRole.objects.none()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return StaffRoleCreateUpdateSerializer
        return StaffRoleSerializer

    def create(self, request, *args, **kwargs):
        if not request.user.has_permission('administration', 'create'):
            return custom_response(
                False, 
                "You don't have permission to create roles", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role != User.Role.SUPER_ADMIN and request.user.company:
            request.data['company'] = request.user.company.id
        
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not request.user.has_permission('administration', 'edit'):
            return custom_response(
                False, 
                "You don't have permission to edit roles", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.has_permission('administration', 'delete'):
            return custom_response(
                False, 
                "You don't have permission to delete roles", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)


# --------------------------
# Staff ViewSet
# --------------------------
class StaffViewSet(BaseCompanyViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.Role.SUPER_ADMIN:
            return Staff.objects.all()
        
        if user.company:
            return Staff.objects.filter(company=user.company)
        
        return Staff.objects.none()

    def create(self, request, *args, **kwargs):
        if not request.user.has_permission('administration', 'create'):
            return custom_response(
                False, 
                "You don't have permission to create staff", 
                None, 
                status.HTTP_403_FORBIDDEN
            )
        
        return super().create(request, *args, **kwargs)


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
            confirm_password = request.data.get('confirm_password')

            if not current_password or not new_password or not confirm_password:
                return custom_response(
                    False, 
                    "All fields are required", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            if new_password != confirm_password:
                return custom_response(
                    False, 
                    "New passwords do not match", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            if not user.check_password(current_password):
                return custom_response(
                    False, 
                    "Current password is incorrect", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            if len(new_password) < 8:
                return custom_response(
                    False, 
                    "New password must be at least 8 characters long", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            user.set_password(new_password)
            user.save()
            logger.info(f"Password changed for user: {user.username}")

            return custom_response(True, "Password changed successfully", None, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}", exc_info=True)
            return custom_response(
                False, 
                "Password change failed", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# --------------------------
# Profile API
# --------------------------
class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            has_staff_profile = hasattr(user, 'staff_profile') and user.staff_profile

            profile_data = {
                'user': UserProfileSerializer(user).data,
                'staff_profile': StaffProfileSerializer(user.staff_profile).data if has_staff_profile else None,
                'permissions': user.get_permissions(),
                'permission_source': user.permission_source,
                'company_info': CompanySerializer(user.company).data if hasattr(user, "company") and user.company else None
            }

            logger.info(f"User profile fetched for: {user.username}")
            return custom_response(
                True, 
                "User profile fetched successfully", 
                profile_data, 
                status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
            return custom_response(
                False, 
                "Error fetching user profile", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):
        try:
            user = request.user
            data = request.data.copy()
            
            # Remove sensitive fields
            sensitive_fields = ['password', 'is_superuser', 'is_staff', 'role', 'company', 'username']
            for field in sensitive_fields:
                data.pop(field, None)

            serializer = UserProfileSerializer(user, data=data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                
                has_staff_profile = hasattr(user, 'staff_profile') and user.staff_profile
                updated_profile_data = {
                    'user': UserProfileSerializer(user).data,
                    'staff_profile': StaffProfileSerializer(user.staff_profile).data if has_staff_profile else None,
                    'permissions': user.get_permissions(),
                    'permission_source': user.permission_source,
                    'company_info': {
                        'id': user.company.id if user.company else None,
                        'name': user.company.name if user.company else None,
                        'plan_type': user.company.plan_type if user.company else None,
                        'is_active': user.company.is_active if user.company else None,
                    } if hasattr(user, "company") and user.company else None
                }
                
                return custom_response(
                    True, 
                    "Profile updated successfully", 
                    updated_profile_data, 
                    status.HTTP_200_OK
                )
            else:
                return custom_response(
                    False, 
                    "Validation error", 
                    serializer.errors, 
                    status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}", exc_info=True)
            return custom_response(
                False, 
                "Error updating profile", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
                'permission_source': user.permission_source,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'permissions': user.get_permissions(),
                'can_manage_users': user.can_manage_user(user),  # Check if can manage self (admin check)
                'can_manage_company': user.role in [user.Role.SUPER_ADMIN, user.Role.ADMIN],
            }
            return custom_response(
                True, 
                "User permissions fetched successfully", 
                permissions_data, 
                status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching user permissions: {str(e)}")
            return custom_response(
                False, 
                "Error fetching permissions", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        try:
            module = request.data.get('module')
            action = request.data.get('action')
            
            if not module:
                return custom_response(
                    False, 
                    "Module is required", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )
            
            has_perm = request.user.has_permission(module, action)
            
            return custom_response(
                True, 
                "Permission check completed", 
                {
                    'has_permission': has_perm,
                    'module': module,
                    'action': action or 'any'
                }, 
                status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error checking permission: {str(e)}")
            return custom_response(
                False, 
                "Error checking permission", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# --------------------------
# Image update endpoints
# --------------------------
class CompanyLogoUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, pk=None, *args, **kwargs):
        try:
            if pk is not None:
                if request.user.role != User.Role.SUPER_ADMIN:
                    return custom_response(
                        False, 
                        "Not authorized to update other company logos", 
                        None, 
                        status.HTTP_403_FORBIDDEN
                    )
                company = get_object_or_404(Company, pk=pk)
            else:
                company = getattr(request.user, 'company', None)
                if not company:
                    return custom_response(
                        False, 
                        "User is not assigned to a company", 
                        None, 
                        status.HTTP_400_BAD_REQUEST
                    )

            file = request.FILES.get('logo')
            if not file:
                return custom_response(
                    False, 
                    "No 'logo' file provided", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            if file.size > 5 * 1024 * 1024:
                return custom_response(
                    False, 
                    "File size should not exceed 5MB", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            content_type = getattr(file, 'content_type', '') or ''
            if not content_type.startswith('image/'):
                return custom_response(
                    False, 
                    "Uploaded file is not an image", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            company.logo = file
            company.save()

            serializer = CompanySerializer(company, context={'request': request})
            return custom_response(
                True, 
                "Company logo updated successfully", 
                serializer.data, 
                status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Company logo update failed")
            return custom_response(
                False, 
                f"Company logo update failed: {str(e)}", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ResetPermissionsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Reset user permissions to role defaults
        Expected JSON: {"user_id": 123}
        """
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'status': False,
                'message': 'user_id is required'
            }, status=400)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'status': False,
                'message': 'User not found'
            }, status=404)
        
        # Check if current user has permission to reset permissions
        if not request.user.has_permission('users', 'edit'):
            return Response({
                'status': False,
                'message': 'You do not have permission to reset user permissions'
            }, status=403)
        
        # Reset user permissions to role defaults
        user.reset_to_role_permissions()
        
        return Response({
            'status': True,
            'message': 'Permissions reset to role defaults successfully',
            'data': {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'permission_source': user.permission_source,
                }
            }
        })



class UserProfileImageUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, pk=None, *args, **kwargs):
        try:
            if pk is not None:
                if request.user.role != User.Role.SUPER_ADMIN:
                    return custom_response(
                        False, 
                        "Not authorized to update other users' profile pictures", 
                        None, 
                        status.HTTP_403_FORBIDDEN
                    )
                target_user = get_object_or_404(User, pk=pk)
            else:
                target_user = request.user

            file = request.FILES.get('profile_picture')
            if not file:
                return custom_response(
                    False, 
                    "No 'profile_picture' file provided", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            if file.size > 2 * 1024 * 1024:
                return custom_response(
                    False, 
                    "File size should not exceed 2MB", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            content_type = getattr(file, 'content_type', '') or ''
            if not content_type.startswith('image/'):
                return custom_response(
                    False, 
                    "Uploaded file is not an image", 
                    None, 
                    status.HTTP_400_BAD_REQUEST
                )

            target_user.profile_picture = file
            target_user.save()

            serializer = UserProfileSerializer(target_user, context={'request': request})
            return custom_response(
                True, 
                "Profile picture updated successfully", 
                serializer.data, 
                status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Profile picture update failed")
            return custom_response(
                False, 
                f"Profile picture update failed: {str(e)}", 
                None, 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            return custom_response(
                False, 
                "User has no company assigned", 
                None, 
                status.HTTP_400_BAD_REQUEST
            )

        try:
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
                    
        except ImportError:
            stats = {
                'today_sales': 0,
                'today_orders': 0,
                'total_products': 0,
                'total_customers': 0,
                'total_suppliers': 0,
                'pending_purchases': 0,
                'due_sales': 0,
            }

        return custom_response(
            True, 
            "Dashboard stats fetched successfully", 
            stats, 
            status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}", exc_info=True)
        return custom_response(
            False, 
            "Error fetching dashboard statistics", 
            None, 
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --------------------------
# Admin Web Views (Optional)
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