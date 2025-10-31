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
        try:
            return request.user.company
        except AttributeError:
            logger.error("User has no company associated")
            raise ValueError("User must be associated with a company")
    
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
        """Standard exception handling"""
        logger.error(f"Report error: {str(exc)}", exc_info=True)
        from reports.utils import custom_response
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
            return queryset.filter(company=user.company)
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