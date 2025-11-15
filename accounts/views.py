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
    # accounts/views.py
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

            # For Cash and Other accounts, number should be None
            if ac_type in [Account.TYPE_CASH, Account.TYPE_OTHER]:
                number = None

            # Check for existing accounts based on type
            if ac_type == Account.TYPE_CASH:
                if Account.objects.filter(company=company, ac_type=Account.TYPE_CASH).exists():
                    return custom_response(
                        success=False,
                        message="A Cash account already exists for your company. You can only have one Cash account.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            elif ac_type == Account.TYPE_OTHER:
                if Account.objects.filter(company=company, ac_type=Account.TYPE_OTHER).exists():
                    return custom_response(
                        success=False,
                        message="An Other account already exists for your company. You can only have one Other account.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            else:
                # For Bank and Mobile banking, check by number
                if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
                    return custom_response(
                        success=False,
                        message="An account with this type and number already exists.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

            # Create the account instance but don't save yet
            account = Account(
                company=company,
                created_by=request.user,
                name=name,
                ac_type=ac_type,
                number=number,
                bank_name=serializer.validated_data.get('bank_name'),
                branch=serializer.validated_data.get('branch'),
                opening_balance=opening_balance,
                balance=opening_balance,  # Set initial balance to opening balance
                is_active=True
            )

            # Store the user for the opening balance transaction
            account._creating_user = request.user

            # Validate and save the account
            account.full_clean()
            account.save()

            # Get the complete account data with serialized response
            serializer = self.get_serializer(account)
            
            logger.info(f"Account created successfully: {account.id} with opening balance: {opening_balance}")
            
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
    # def create(self, request, *args, **kwargs):
    #     serializer = self.get_serializer(data=request.data)
    #     try:
    #         serializer.is_valid(raise_exception=True)
    #         company = self.request.user.company
    #         ac_type = serializer.validated_data.get('ac_type')
    #         number = serializer.validated_data.get('number')
    #         name = serializer.validated_data.get('name')
    #         opening_balance = serializer.validated_data.get('opening_balance', Decimal('0.00'))


    #         # Handle empty string as None for uniqueness check
    #         if number == '':
    #             number = None

    #         # For Cash and Other accounts, number should be None
    #         if ac_type in [Account.TYPE_CASH, Account.TYPE_OTHER]:
    #             number = None

    #         # Check for existing accounts based on type
    #         if ac_type == Account.TYPE_CASH:
    #             if Account.objects.filter(company=company, ac_type=Account.TYPE_CASH).exists():
    #                 return custom_response(
    #                     success=False,
    #                     message="A Cash account already exists for your company. You can only have one Cash account.",
    #                     data=None,
    #                     status_code=status.HTTP_400_BAD_REQUEST
    #                 )
            
    #         elif ac_type == Account.TYPE_OTHER:
    #             if Account.objects.filter(company=company, ac_type=Account.TYPE_OTHER).exists():
    #                 return custom_response(
    #                     success=False,
    #                     message="An Other account already exists for your company. You can only have one Other account.",
    #                     data=None,
    #                     status_code=status.HTTP_400_BAD_REQUEST
    #                 )
            
    #         else:
    #             # For Bank and Mobile banking, check by number
    #             if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
    #                 return custom_response(
    #                     success=False,
    #                     message="An account with this type and number already exists.",
    #                     data=None,
    #                     status_code=status.HTTP_400_BAD_REQUEST
    #                 )

    #         instance = serializer.save(company=company, created_by=request.user)

    #         logger.info(f"Account created successfully: {instance.id}")
            
    #         return custom_response(
    #             success=True,
    #             message="Account created successfully.",
    #             data=self.get_serializer(instance).data,
    #             status_code=status.HTTP_201_CREATED
    #         )

    #     except serializers.ValidationError as e:
    #         logger.warning(f"Account validation error: {e.detail}")
    #         return custom_response(
    #             success=False,
    #             message="Validation Error",
    #             data=e.detail,
    #             status_code=status.HTTP_400_BAD_REQUEST
    #         )
    #     except Exception as e:
    #         logger.error(f"Error creating account: {str(e)}", exc_info=True)
    #         return custom_response(
    #             success=False,
    #             message="Internal server error",
    #             data=None,
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
  
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        try:
            serializer.is_valid(raise_exception=True)
            company = self.request.user.company
            ac_type = serializer.validated_data.get('ac_type')
            number = serializer.validated_data.get('number')

            # Fix: Handle empty string as None for uniqueness check
            if number == '':
                number = None

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
                data=self.get_serializer(updated_instance).data,
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
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """
        Delete an account - Only allow if no transactions or related records exist
        """
        try:
            instance = self.get_object()
            account_name = instance.name
            
            # Check all possible relationships that might prevent deletion
            blocking_relationships = []
            
            # 1. Check for transactions
            if hasattr(instance, 'transactions') and instance.transactions.exists():
                blocking_relationships.append(f"{instance.transactions.count()} transactions")
            
            # 2. Check for money receipts
            if hasattr(instance, 'money_receipts') and instance.money_receipts.exists():
                blocking_relationships.append(f"{instance.money_receipts.count()} money receipts")
            
            # 3. Check for supplier payments
            if hasattr(instance, 'supplier_payments') and instance.supplier_payments.exists():
                blocking_relationships.append(f"{instance.supplier_payments.count()} supplier payments")
            
            # 4. Check for sales
            if hasattr(instance, 'sales') and instance.sales.exists():
                blocking_relationships.append(f"{instance.sales.count()} sales")
            
            # 5. Check for purchases
            if hasattr(instance, 'purchases') and instance.purchases.exists():
                blocking_relationships.append(f"{instance.purchases.count()} purchases")
            
            # 6. Check for expenses
            if hasattr(instance, 'expenses') and instance.expenses.exists():
                blocking_relationships.append(f"{instance.expenses.count()} expenses")
            
            # 7. Additional checks for other possible relationships
            # Check if account is used in any sale payments
            try:
                from sales.models import SalePayment
                sale_payments_count = SalePayment.objects.filter(account=instance).count()
                if sale_payments_count > 0:
                    blocking_relationships.append(f"{sale_payments_count} sale payments")
            except (ImportError, Exception):
                pass
            
            # Check if account is used in any purchase payments
            try:
                from purchases.models import PurchasePayment
                purchase_payments_count = PurchasePayment.objects.filter(account=instance).count()
                if purchase_payments_count > 0:
                    blocking_relationships.append(f"{purchase_payments_count} purchase payments")
            except (ImportError, Exception):
                pass
            
            # Check if account is used in any expense payments
            try:
                from expenses.models import ExpensePayment
                expense_payments_count = ExpensePayment.objects.filter(account=instance).count()
                if expense_payments_count > 0:
                    blocking_relationships.append(f"{expense_payments_count} expense payments")
            except (ImportError, Exception):
                pass
            
            # Check if account is used in any journal entries
            try:
                from accounting.models import JournalEntry
                journal_entries_count = JournalEntry.objects.filter(
                    Q(debit_account=instance) | Q(credit_account=instance)
                ).count()
                if journal_entries_count > 0:
                    blocking_relationships.append(f"{journal_entries_count} journal entries")
            except (ImportError, Exception):
                pass
            
            # Check if account is used in any fund transfers
            try:
                from transfers.models import FundTransfer
                fund_transfers_count = FundTransfer.objects.filter(
                    Q(from_account=instance) | Q(to_account=instance)
                ).count()
                if fund_transfers_count > 0:
                    blocking_relationships.append(f"{fund_transfers_count} fund transfers")
            except (ImportError, Exception):
                pass
            
            # If any blocking relationships exist, mark as inactive instead of deleting
            if blocking_relationships:
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                
                # Create detailed message
                relationships_text = ", ".join(blocking_relationships)
                message = f"Account cannot be deleted as it has {relationships_text}. It has been marked as inactive instead."
                
                logger.warning(f"Account deletion blocked for '{account_name}'. Reasons: {relationships_text}")
                
                return custom_response(
                    success=True,
                    message=message,
                    data={
                        'is_active': instance.is_active,
                        'blocking_relationships': blocking_relationships,
                        'account_id': instance.id,
                        'account_name': account_name
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # If no blocking relationships, proceed with actual deletion
            instance.delete()
            
            logger.info(f"Account deleted successfully: {account_name} (ID: {instance.id})")
            
            return custom_response(
                success=True,
                message=f"Account '{account_name}' deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
                
        except Exception as e:
            logger.error(f"Error deleting account: {str(e)}", exc_info=True)
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



