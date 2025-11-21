from rest_framework import status, serializers
from rest_framework.decorators import action
from django.db.models import Q, Sum, Count, DecimalField
from core.base_viewsets import BaseCompanyViewSet, BaseInventoryViewSet
from core.pagination import CustomPageNumberPagination
from core.utils import custom_response
from .models import Account
from .serializers import AccountSerializer  # Fixed import
import logging
# Add these imports at the top of your views.py file
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




logger = logging.getLogger(__name__)

class AccountViewSet(BaseInventoryViewSet):
    """CRUD API for accounts with company-based filtering, pagination control, and search."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    search_fields = ['name', 'number', 'bank_name', 'branch', 'ac_type']
    ordering_fields = ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch']
    ordering = ['ac_no']
    
    def get_queryset(self):
        """Apply filters and search to the queryset"""
        # Start with base queryset
        queryset = super().get_queryset()
        
        # Debug: Log initial state
        logger.debug(f"=== ACCOUNT FILTER DEBUG ===")
        logger.debug(f"Initial queryset count: {queryset.count()}")
        logger.debug(f"All account types in DB: {list(queryset.values_list('ac_type', flat=True).distinct())}")
        
        # Get filter parameters
        ac_type = self.request.query_params.get('ac_type')
        logger.debug(f"Requested ac_type filter: '{ac_type}'")
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Account.objects.none()
        # Apply company filtering (CRITICAL - add this)
        if hasattr(self.request, 'user') and hasattr(self.request.user, 'company'):
            queryset = queryset.filter(company=self.request.user.company)
            logger.debug(f"After company filter count: {queryset.count()}")
            logger.debug(f"Account types after company filter: {list(queryset.values_list('ac_type', flat=True).distinct())}")
        
        # Apply filters - FIX: Use case-insensitive filtering
        if ac_type:
            logger.debug(f"Applying ac_type filter: '{ac_type}'")
            # Case-insensitive filter
            queryset = queryset.filter(ac_type__iexact=ac_type)
            logger.debug(f"After ac_type filter count: {queryset.count()}")
            
        # ... rest of your existing filtering code ...
        
        search = self.request.query_params.get('search')
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
            
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(number__icontains=search) |
                Q(bank_name__icontains=search) |
                Q(branch__icontains=search)
            )
            
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
        
        # Order by name by default
        order_by = self.request.query_params.get('order_by', 'name')
        if order_by.lstrip('-') in ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('name')
            
        logger.debug(f"Final queryset count: {queryset.count()}")
        logger.debug(f"=== END DEBUG ===")
            
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
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            
            # Apply pagination (use DRF's built-in pagination)
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = self._process_account_data(serializer.data)
                
                # Get the paginated response and extract data
                paginated_response = self.get_paginated_response(data)
                
                # Convert to your custom response format with pagination metadata
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
            elif item.get('number') in ('', None):
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
                message="Internal server error",
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
            name = serializer.validated_data.get('name')
            opening_balance = serializer.validated_data.get('opening_balance', Decimal('0.00'))

            # Handle empty string as None for uniqueness check
            if number == '':
                number = None

            # REMOVED: The restriction that prevents Cash/Other accounts from having numbers
            # Now Cash accounts can have numbers to distinguish between multiple counters

            # Check for existing accounts based on type AND number
            # For ALL account types, check if same type AND same number already exists
            if number:
                # If number is provided, check for duplicate (type + number)
                if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
                    return custom_response(
                        success=False,
                        message="An account with this type and number already exists.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # If no number provided, check for duplicate (type + no number)
                # This prevents multiple "generic" accounts of the same type without numbers
                if Account.objects.filter(company=company, ac_type=ac_type, number__isnull=True).exists():
                    return custom_response(
                        success=False,
                        message=f"A {ac_type} account without a number already exists. Please provide a unique account number.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Create the account instance - set balance to opening_balance
            account = Account(
                company=company,
                created_by=request.user,
                name=name,
                ac_type=ac_type,
                number=number,  # This will now preserve your account numbers for Cash accounts
                bank_name=serializer.validated_data.get('bank_name'),
                branch=serializer.validated_data.get('branch'),
                opening_balance=opening_balance,
                balance=opening_balance,
                is_active=True
            )

            # Validate and save the account with the creating user
            account.full_clean()
            account.save(creating_user=request.user)

            # Get the complete account data with serialized response
            serializer = self.get_serializer(account)
            
            logger.info(f"✅ Account created successfully: {account.id} with opening balance: {opening_balance}")
            logger.info(f"✅ Account '{account.name}' final balance: {account.balance}")
            
            return custom_response(
                success=True,
                message="Account created successfully." + (f" Opening balance transaction created." if opening_balance > 0 else ""),
                data=serializer.data,
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
            
            company = request.user.company
            ac_type = serializer.validated_data.get('ac_type')
            number = serializer.validated_data.get('number')
            name = serializer.validated_data.get('name')
            
            # Handle empty string as None
            if number == '':
                number = None
            
            # REMOVED: The restriction that forces Cash/Other accounts to have null numbers
            # Now Cash accounts can have numbers to distinguish between multiple counters
            
            # Check for duplicates (excluding current instance)
            if number:
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
            else:
                # Check for other accounts of same type without number
                if Account.objects.filter(
                    company=company, 
                    ac_type=ac_type, 
                    number__isnull=True
                ).exclude(id=instance.id).exists():
                    return custom_response(
                        success=False,
                        message=f"A {ac_type} account without a number already exists.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # Update the instance
            instance.name = name
            instance.ac_type = ac_type
            instance.number = number  # This will now preserve the account number
            instance.bank_name = serializer.validated_data.get('bank_name')
            instance.branch = serializer.validated_data.get('branch')
            
            instance.save()
            
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
            logger.debug(f"=== PARTIAL UPDATE DEBUG ===")
            logger.debug(f"Updating account ID: {instance.id}")
            logger.debug(f"Current account data - Name: {instance.name}, Type: {instance.ac_type}, Number: {instance.number}")
            logger.debug(f"Request data: {request.data}")
            
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            company = request.user.company
            validated_data = serializer.validated_data
            
            logger.debug(f"Validated data: {validated_data}")
            
            # Handle number field
            if 'number' in validated_data:
                number = validated_data['number']
                logger.debug(f"Number from request: '{number}'")
                if number == '':
                    number = None
                validated_data['number'] = number
                logger.debug(f"Number after processing: '{number}'")
            
            # Check for duplicates if type or number is being updated
            ac_type = validated_data.get('ac_type', instance.ac_type)
            number = validated_data.get('number', instance.number)
            
            logger.debug(f"Final values - Type: {ac_type}, Number: {number}")
            
            # REMOVED: The restriction that forces Cash/Other accounts to have null numbers
            # Make sure this line is NOT in your code:
            # if ac_type in [Account.TYPE_CASH, Account.TYPE_OTHER]: number = None
            
            # Check for duplicates (excluding current instance)
            if number:
                if Account.objects.filter(
                    company=company, 
                    ac_type=ac_type, 
                    number=number
                ).exclude(id=instance.id).exists():
                    logger.debug("Duplicate account found with same type and number")
                    return custom_response(
                        success=False,
                        message="An account with this type and number already exists.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            else:
                if ac_type != instance.ac_type or 'ac_type' in validated_data:
                    # Only check if type is changing or being set
                    if Account.objects.filter(
                        company=company, 
                        ac_type=ac_type, 
                        number__isnull=True
                    ).exclude(id=instance.id).exists():
                        logger.debug("Duplicate account found with same type and no number")
                        return custom_response(
                            success=False,
                            message=f"A {ac_type} account without a number already exists.",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
            
            # Update the instance
            for attr, value in validated_data.items():
                logger.debug(f"Setting {attr} = {value}")
                setattr(instance, attr, value)
            
            logger.debug(f"Before save - Name: {instance.name}, Type: {instance.ac_type}, Number: {instance.number}")
            instance.save()
            logger.debug(f"After save - Name: {instance.name}, Type: {instance.ac_type}, Number: {instance.number}")
            
            # Return updated data
            updated_serializer = self.get_serializer(instance)
            data = self._process_account_data([updated_serializer.data])[0]
            
            logger.debug(f"=== END PARTIAL UPDATE DEBUG ===")
            
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
        
        
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get only active accounts with pagination control
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.get_queryset().filter(is_active=True)
            queryset = self.filter_queryset(queryset)
            
            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                data = self._process_account_data(serializer.data)
                
                return custom_response(
                    success=True,
                    message=f"Active accounts fetched successfully (no pagination). Total: {queryset.count()}",
                    data={
                        'results': data,
                        'count': queryset.count(),
                        'pagination': 'disabled'
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # Paginated response
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = self._process_account_data(serializer.data)
                return self.get_paginated_response(data)
                
            serializer = self.get_serializer(queryset, many=True)
            data = self._process_account_data(serializer.data)
            
            return custom_response(
                success=True,
                message="Active accounts fetched successfully.",
                data={
                    'results': data,
                    'count': len(data),
                    'pagination': 'not_applied'
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching active accounts: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def inactive(self, request):
        """
        Get only inactive accounts with pagination control
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.get_queryset().filter(is_active=False)
            queryset = self.filter_queryset(queryset)
            
            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                data = self._process_account_data(serializer.data)
                
                return custom_response(
                    success=True,
                    message=f"Inactive accounts fetched successfully (no pagination). Total: {queryset.count()}",
                    data={
                        'results': data,
                        'count': queryset.count(),
                        'pagination': 'disabled'
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # Paginated response
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = self._process_account_data(serializer.data)
                return self.get_paginated_response(data)
                
            serializer = self.get_serializer(queryset, many=True)
            data = self._process_account_data(serializer.data)
            
            return custom_response(
                success=True,
                message="Inactive accounts fetched successfully.",
                data={
                    'results': data,
                    'count': len(data),
                    'pagination': 'not_applied'
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching inactive accounts: {str(e)}", exc_info=True)
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
            total_balance = queryset.aggregate(total=Sum('balance'))['total'] or 0
            
            # Count by account type
            type_count = queryset.values('ac_type').annotate(
                count=Count('id'),
                total_balance=Sum('balance')
            )
            
            # Count by status (using is_active field)
            status_count = queryset.values('is_active').annotate(
                count=Count('id')
            )
            
            # Convert status count to more readable format
            status_breakdown = []
            for item in status_count:
                status_breakdown.append({
                    'status': 'Active' if item['is_active'] else 'Inactive',
                    'count': item['count']
                })
            
            summary_data = {
                'total_accounts': total_accounts,
                'total_balance': float(total_balance),
                'account_type_breakdown': list(type_count),
                'status_breakdown': status_breakdown
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



