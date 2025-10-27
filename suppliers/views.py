# suppliers/views.py
from rest_framework import viewsets, status, permissions, serializers
from django.db.models import Q
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .models import Supplier  # Import from models, not defined here
from .serializers import SupplierSerializer
import logging

logger = logging.getLogger(__name__)
from core.views import BaseCompanyViewSet

class SupplierViewSet(BaseCompanyViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Apply filters and search to the queryset"""
        queryset = super().get_queryset()
        
        # Get filter parameters
        search = self.request.query_params.get('search')
        status_filter = self.request.query_params.get('status')
        
        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(supplier_no__icontains=search) |
                Q(name__icontains=search) |
                Q(address__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
            
        if status_filter:
            if status_filter.lower() == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter.lower() == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Order by name by default
        order_by = self.request.query_params.get('order_by', 'name')
        if order_by.lstrip('-') in ['name', 'email', 'created_at', 'updated_at', 'total_purchases']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('name')
            
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # If no pagination, return all results
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Supplier list fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching supplier list: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            supplier = self.get_object()
            serializer = self.get_serializer(supplier)
            return custom_response(
                success=True,
                message="Supplier details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching supplier details: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check for duplicate supplier name in the same company
            name = serializer.validated_data.get('name')
            if Supplier.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A supplier with this name already exists in your company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            instance = serializer.save(company=company, created_by=request.user)
            logger.info(f"Supplier created successfully: {instance.id}")
            
            return custom_response(
                success=True,
                message="Supplier created successfully.",
                data=SupplierSerializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            logger.warning(f"Supplier validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating supplier: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            
            # Check for duplicate supplier name (excluding current instance)
            name = serializer.validated_data.get('name')
            if Supplier.objects.filter(company=company, name=name).exclude(id=instance.id).exists():
                return custom_response(
                    success=False,
                    message="A supplier with this name already exists in your company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            updated_instance = serializer.save()
            logger.info(f"Supplier updated successfully: {instance.id}")
            
            return custom_response(
                success=True,
                message="Supplier updated successfully.",
                data=SupplierSerializer(updated_instance).data,
                status_code=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            logger.warning(f"Supplier update validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating supplier: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            supplier_id = instance.id
            supplier_name = instance.name
            instance.delete()
            
            logger.info(f"Supplier deleted successfully: {supplier_id} - {supplier_name}")
            
            return custom_response(
                success=True,
                message="Supplier deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error deleting supplier: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )