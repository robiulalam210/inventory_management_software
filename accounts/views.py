from rest_framework import status, serializers
from rest_framework.decorators import action
from django.db.models import Q, Sum, Count, DecimalField
from core.base_viewsets import BaseCompanyViewSet, BaseInventoryViewSet
from core.pagination import CustomPageNumberPagination
from core.utils import custom_response
from .models import Account
from .serializers import AccountSerializer
import logging
from rest_framework import viewsets, status, serializers, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Case, When, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from core.utils import custom_response
from django.http import Http404

logger = logging.getLogger(__name__)


class AccountViewSet(BaseInventoryViewSet):
    """CRUD API for accounts with company-based filtering, pagination control, and search."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    search_fields = ['name', 'number', 'bank_name', 'branch', 'ac_type']
    ordering_fields = ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Apply filters and search to the queryset"""
        # Start with base queryset
        queryset = super().get_queryset()
        
        # Always filter by company
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Account.objects.none()
        
        # Apply account type filter
        ac_type = self.request.query_params.get('ac_type')
        if ac_type:
            queryset = queryset.filter(ac_type__iexact=ac_type)
        
        # Apply search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(number__icontains=search) |
                Q(bank_name__icontains=search) |
                Q(branch__icontains=search) |
                Q(ac_no__icontains=search)
            )
        
        # Apply balance filters
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
        
        if min_balance:
            try:
                queryset = queryset.filter(balance__gte=Decimal(min_balance))
            except (ValueError, TypeError):
                pass
        
        if max_balance:
            try:
                queryset = queryset.filter(balance__lte=Decimal(max_balance))
            except (ValueError, TypeError):
                pass
        
        # Apply status filter
        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter.lower() == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter.lower() == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Ordering
        order_by = self.request.query_params.get('order_by', '-created_at')
        if order_by.lstrip('-') in ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch', 'ac_no']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-created_at')
            
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Get accounts with pagination control and filtering
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.filter_queryset(self.get_queryset())
            
            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                data = self._process_account_data(serializer.data)
                
                return custom_response(
                    success=True,
                    message=f"Accounts fetched successfully (no pagination). Total: {queryset.count()}",
                    data={
                        'results': data,
                        'count': queryset.count(),
                        'pagination': 'disabled'
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = self._process_account_data(serializer.data)
                
                # Get the paginated response
                paginated_response = self.get_paginated_response(data)
                response_data = paginated_response.data
                
                return custom_response(
                    success=True,
                    message=f"Accounts fetched successfully. Total: {response_data.get('count', 0)}",
                    data={
                        'results': response_data.get('results', []),
                        'count': response_data.get('count', 0),
                        'total_pages': response_data.get('total_pages', 1),
                        'current_page': response_data.get('current_page', 1),
                        'page_size': response_data.get('page_size', 10),
                        'next': response_data.get('next'),
                        'previous': response_data.get('previous'),
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # Fallback if pagination is not active
            serializer = self.get_serializer(queryset, many=True)
            data = self._process_account_data(serializer.data)
            
            return custom_response(
                success=True,
                message="Account list fetched successfully.",
                data={
                    'results': data,
                    'count': len(data),
                    'total_pages': 1,
                    'current_page': 1,
                    'page_size': len(data),
                    'next': None,
                    'previous': None,
                },
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching account list: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_account_data(self, data):
        """Process account data to ensure consistent format"""
        for item in data:
            # Ensure number is None if blank or empty string
            if item.get('ac_number') in ('', None):
                item['ac_number'] = None
            
            # Ensure balance is float
            if 'balance' in item and item['balance'] is not None:
                item['balance'] = float(item['balance'])
                
            # Ensure opening_balance is float
            if 'opening_balance' in item and item['opening_balance'] is not None:
                item['opening_balance'] = float(item['opening_balance'])
                
            # Ensure bank_name and branch are None if empty
            if item.get('bank_name') in ('', None):
                item['bank_name'] = None
                
            if item.get('branch') in ('', None):
                item['branch'] = None
                
            # Add status field
            if 'is_active' in item:
                item['status'] = 'Active' if item['is_active'] else 'Inactive'
                
        return data

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            data = self._process_account_data([serializer.data])[0]
            
            return custom_response(
                success=True,
                message="Account details fetched successfully.",
                data=data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching account details: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            account = serializer.save()
            
            
            # Get the serialized data
            response_serializer = self.get_serializer(account)
            data = self._process_account_data([response_serializer.data])[0]
            
            return custom_response(
                success=True,
                message="Account created successfully." + (f" Opening balance transaction created." if account.opening_balance > 0 else ""),
                data=data,
                status_code=status.HTTP_201_CREATED
            )

        except serializers.ValidationError as e:
            logger.warning(f"Account validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating account: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
  
    def update(self, request, *args, **kwargs):
        """
        Update an existing account
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=False)
            serializer.is_valid(raise_exception=True)
            
            # Update the instance
            serializer.save()
            
            # Return updated data
            updated_serializer = self.get_serializer(instance)
            data = self._process_account_data([updated_serializer.data])[0]
            
            return custom_response(
                success=True,
                message="Account updated successfully.",
                data=data,
                status_code=status.HTTP_200_OK
            )
            
        except Http404:
            logger.warning(f"Account not found for update: {kwargs.get('pk')}")
            return custom_response(
                success=False,
                message="Account not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except serializers.ValidationError as e:
            logger.warning(f"Account update validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating account: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def partial_update(self, request, *args, **kwargs):
        """
        Partial update of an account
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            # Update the instance
            serializer.save()
            
            # Return updated data
            updated_serializer = self.get_serializer(instance)
            data = self._process_account_data([updated_serializer.data])[0]
            
            return custom_response(
                success=True,
                message="Account updated successfully.",
                data=data,
                status_code=status.HTTP_200_OK
            )
            
        except Http404:
            logger.warning(f"Account not found for update: {kwargs.get('pk')}")
            return custom_response(
                success=False,
                message="Account not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except serializers.ValidationError as e:
            logger.warning(f"Account partial update validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error partially updating account: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle account active status"""
        try:
            instance = self.get_object()
            instance.is_active = not instance.is_active
            instance.save()
            
            status_text = "activated" if instance.is_active else "deactivated"
            
            return custom_response(
                success=True,
                message=f"Account {status_text} successfully.",
                data={'id': instance.id, 'is_active': instance.is_active},
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error toggling account status: {str(e)}")
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """Get available account types"""
        try:
            types_list = [
                {'value': Account.TYPE_BANK, 'label': 'Bank'},
                {'value': Account.TYPE_MOBILE, 'label': 'Mobile banking'},
                {'value': Account.TYPE_CASH, 'label': 'Cash'},
                {'value': Account.TYPE_OTHER, 'label': 'Other'}
            ]
            
            return custom_response(
                success=True,
                message="Account types fetched successfully.",
                data=types_list,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching account types: {str(e)}")
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get account summary statistics"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            total_accounts = queryset.count()
            total_balance = queryset.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
            
            # Count by account type
            type_count = queryset.values('ac_type').annotate(
                count=Count('id'),
                total_balance=Sum('balance')
            ).order_by('ac_type')
            
            # Count by status
            active_count = queryset.filter(is_active=True).count()
            inactive_count = total_accounts - active_count
            
            summary_data = {
                'total_accounts': total_accounts,
                'total_balance': float(total_balance),
                'account_type_breakdown': [
                    {
                        'ac_type': item['ac_type'],
                        'count': item['count'],
                        'total_balance': float(item['total_balance'] or Decimal('0.00'))
                    }
                    for item in type_count
                ],
                'status_breakdown': [
                    {'status': 'Active', 'count': active_count},
                    {'status': 'Inactive', 'count': inactive_count}
                ]
            }
            
            return custom_response(
                success=True,
                message="Account summary fetched successfully.",
                data=summary_data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching account summary: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )