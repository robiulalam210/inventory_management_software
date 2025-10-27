from rest_framework import status, serializers
from rest_framework.decorators import action
from django.db.models import Q, Sum, Count
from core.base_viewsets import BaseCompanyViewSet
from core.pagination import CustomPageNumberPagination
from core.utils import custom_response
from .models import Account
from .serializers import AccountSerializer
import logging

logger = logging.getLogger(__name__)

class AccountViewSet(BaseCompanyViewSet):
    """CRUD API for accounts with company-based filtering, pagination, and search."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Apply filters and search to the queryset"""
        queryset = super().get_queryset()
        
        # Get filter parameters
        ac_type = self.request.query_params.get('ac_type')
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
        
        # Apply filters
        if ac_type:
            queryset = queryset.filter(ac_type=ac_type)
            
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(number__icontains=search) |
                Q(bank_name__icontains=search) |  # Added bank_name to search
                Q(branch__icontains=search)       # Added branch to search
            )
            
        if min_balance:
            queryset = queryset.filter(balance__gte=min_balance)
            
        if max_balance:
            queryset = queryset.filter(balance__lte=max_balance)
        
        # Order by name by default
        order_by = self.request.query_params.get('order_by', 'name')
        if order_by.lstrip('-') in ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch']:
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
                data = self._process_account_data(serializer.data)
                return self.get_paginated_response(data)
            
            # If no pagination, return all results
            serializer = self.get_serializer(queryset, many=True)
            data = self._process_account_data(serializer.data)
            
            return custom_response(
                success=True,
                message="Account list fetched successfully.",
                data=data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching account list: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_account_data(self, data):
        """Process account data to ensure consistent format"""
        for item in data:
            # Ensure number is None if blank or empty string
            if item.get('number') in ('', None):
                item['number'] = None
                
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
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = self.request.user.company
            ac_type = serializer.validated_data.get('ac_type')
            number = serializer.validated_data.get('number')

            # Uniqueness check for the same company, type, and number
            if Account.objects.filter(
                company=company, 
                ac_type=ac_type, 
                number=number
            ).exists():
                return custom_response(
                    success=False,
                    message="An account with this type and number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            instance = serializer.save(company=company)

            # Initialize balance if not set
            if instance.balance is None:
                instance.balance = instance.opening_balance or 0
                instance.save()

            logger.info(f"Account created successfully: {instance.id}")
            
            return custom_response(
                success=True,
                message="Account created successfully.",
                data=AccountSerializer(instance).data,
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
            company = self.request.user.company
            ac_type = serializer.validated_data.get('ac_type')
            number = serializer.validated_data.get('number')

            # Uniqueness check (exclude current instance)
            if Account.objects.filter(
                company=company, 
                ac_type=ac_type, 
                number=number
            ).exclude(id=instance.id).exists():
                return custom_response(
                    success=False,
                    message="An account with this type and number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            updated_instance = serializer.save()

            logger.info(f"Account updated successfully: {instance.id}")
            
            return custom_response(
                success=True,
                message="Account updated successfully.",
                data=AccountSerializer(updated_instance).data,
                status_code=status.HTTP_200_OK
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
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            account_id = instance.id
            instance.delete()
            
            logger.info(f"Account deleted successfully: {account_id}")
            
            return custom_response(
                success=True,
                message="Account deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error deleting account: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get account summary statistics"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            total_accounts = queryset.count()
            total_balance = queryset.aggregate(total=Sum('balance'))['total'] or 0
            
            # Count by account type
            type_count = queryset.values('ac_type').annotate(
                count=Count('id'),
                total_balance=Sum('balance')
            )
            
            # Count by status
            status_count = queryset.values('status').annotate(
                count=Count('id')
            )
            
            summary_data = {
                'total_accounts': total_accounts,
                'total_balance': float(total_balance),
                'account_type_breakdown': list(type_count),
                'status_breakdown': list(status_count)
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
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )