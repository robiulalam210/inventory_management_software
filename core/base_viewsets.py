# core/base_viewsets.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.response import Response
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
import logging
from rest_framework import viewsets, serializers

from rest_framework import viewsets, status
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import logging

logger = logging.getLogger(__name__)

class ReportPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class BaseReportView(APIView):
    permission_classes = [IsAuthenticated]
    filter_serializer_class = None
    cache_timeout = 300
    pagination_class = ReportPagination
    
    def get_company(self, request):
        """Get company from request user"""
        company = getattr(request.user, 'company', None)
        if company is None:
            # Super Admin এর নিজের কোম্পানি নেই — তার জন্য দোকানের report হয় না
            raise ValueError("User must be associated with a company")
        return company
    
    def get_filters(self, request):
        """Validate and return filters"""
        if self.filter_serializer_class:
            serializer = self.filter_serializer_class(data=request.GET)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data
        return {}
    
    def get_date_range(self, request):
        """Get date range with predefined range support"""
        from reports.utils import get_date_range, get_predefined_range
        
        # Check for predefined ranges first
        start, end = get_predefined_range(request)
        if start and end:
            return start, end
        
        # Fall back to custom date range
        return get_date_range(request)
    
    def paginate_data(self, data):
        """Paginate data if pagination class is set"""
        if self.pagination_class and isinstance(data, list):
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(data, self.request)
            if page is not None:
                return paginator.get_paginated_response(page).data
        return data
    
    def handle_exception(self, exc):
        """
        লগইন / অনুমতির ভুল আসল status এ ফেরত যায় (401 / 403) — অ্যাপ 401 পেলে token নবায়ন করে।
        আগে সব কিছু 400 হত, ফলে মেয়াদ শেষ token এ রিপোর্ট খুললে অ্যাপ নিজে ঠিক হত না।
        শুধু অপ্রত্যাশিত ভুল error log এ যায়।
        """
        from rest_framework import exceptions as drf_exc
        from reports.utils import custom_response
        if isinstance(exc, (drf_exc.NotAuthenticated, drf_exc.AuthenticationFailed)):
            return super().handle_exception(exc)
        if isinstance(exc, drf_exc.APIException):
            return custom_response(False, str(exc.detail) if isinstance(exc.detail, str) else str(exc), None, exc.status_code)
        logger.error(f"Report error: {str(exc)}", exc_info=True)
        return custom_response(False, str(exc), None, 400)
    

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """
    Base viewset that automatically filters by company and handles user authentication
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Check if user is authenticated
        if not user.is_authenticated:
            return queryset.none()
            
        # Check if user has a company
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
            # শাখা (core/branches.py): যে model এ শাখা আছে (বিক্রি, ক্রয়) সেটা বাছা শাখা অনুযায়ী ছাঁকা
            # (মালিক বাছলে শুধু তালিকা ছাঁকা হয় — অন্য শাখার ইনভয়েস লিংক থেকে খুললে যেন খোলে; শাখায় বসানো স্টাফের সব কিছুই ছাঁকা)
            if any(f.name == 'branch' for f in queryset.model._meta.get_fields()):
                from core.branches import branch_state, filter_qs
                if getattr(self, 'action', None) == 'list' or branch_state(self.request).get('locked'):
                    queryset = filter_qs(queryset, 'branch', self.request)
            return queryset
        else:
            return queryset.none()

    def perform_create(self, serializer):
        """Automatically set company and created_by during creation"""
        user = self.request.user
        
        if not user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")
            
        if not hasattr(user, 'company') or not user.company:
            raise serializers.ValidationError("User does not have an associated company")
            
        serializer.save(company=user.company, created_by=user)




class BaseInventoryViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for all inventory models with common functionality
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ['-created_at']  # Default ordering
    
    def get_queryset(self):
        """
        Base queryset that filters by company and handles active/inactive
        Override in child classes for specific needs
        """
        queryset = super().get_queryset()
        
        # Filter by user's company if user has company
        if hasattr(self.request.user, 'company') and self.request.user.company:
            queryset = queryset.filter(company=self.request.user.company)
        
        # Handle active/inactive filtering from URL parameters
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)
        
        return queryset

    def perform_create(self, serializer):
        """
        Automatically set company and created_by for new objects
        """
        if hasattr(self.request.user, 'company') and self.request.user.company:
            serializer.save(company=self.request.user.company, created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """
        Automatically set updated_by for modified objects
        """
        serializer.save(updated_by=self.request.user)
