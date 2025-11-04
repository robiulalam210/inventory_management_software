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
import logging
logger = logging.getLogger(__name__)

class AccountViewSet(BaseInventoryViewSet):
    """CRUD API for accounts with company-based filtering, pagination control, and search."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    search_fields = ['name', 'number', 'bank_name', 'branch', 'ac_type']
    ordering_fields = ['name', 'ac_type', 'balance', 'created_at', 'number', 'bank_name', 'branch']
    ordering = ['name']
    filterset_fields = ['ac_type', 'is_active']

    def get_queryset(self):
        """Apply filters and search to the queryset"""
        queryset = super().get_queryset()
        
        # Get filter parameters
        ac_type = self.request.query_params.get('ac_type')
        search = self.request.query_params.get('search')
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
        
        # Apply filters
        if ac_type:
            queryset = queryset.filter(ac_type=ac_type)
            
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
            
            # Apply pagination (use DRF's built-in pagination)
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                data = self._process_account_data(serializer.data)
                return self.get_paginated_response(data)
            
            # Fallback if pagination is not active
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

            instance = serializer.save(company=company, created_by=request.user)

            logger.info(f"Account created successfully: {instance.id}")
            
            return custom_response(
                success=True,
                message="Account created successfully.",
                data=self.get_serializer(instance).data,
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
        Delete an account - Only allow if no transactions exist
        """
        try:
            instance = self.get_object()
            account_name = instance.name
            
            # Check if account has any transactions
            has_transactions = hasattr(instance, 'transactions') and instance.transactions.exists()
            
            # Check if account has any money receipts
            has_money_receipts = hasattr(instance, 'money_receipts') and instance.money_receipts.exists()
            
            # Check if account has any supplier payments
            has_supplier_payments = hasattr(instance, 'supplier_payments') and instance.supplier_payments.exists()
            
            # Check if account has any sales or purchases
            has_sales = hasattr(instance, 'sales') and instance.sales.exists()
            has_purchases = hasattr(instance, 'purchases') and instance.purchases.exists()
            
            if has_transactions or has_money_receipts or has_supplier_payments or has_sales or has_purchases:
                # Instead of deleting, mark as inactive
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                
                message = "Account cannot be deleted as it has transaction history. It has been marked as inactive instead."
                if has_transactions:
                    message = "Account cannot be deleted as it has transactions. It has been marked as inactive instead."
                elif has_money_receipts:
                    message = "Account cannot be deleted as it has money receipts. It has been marked as inactive instead."
                elif has_supplier_payments:
                    message = "Account cannot be deleted as it has supplier payments. It has been marked as inactive instead."
                
                return custom_response(
                    success=True,
                    message=message,
                    data={'is_active': instance.is_active},
                    status_code=status.HTTP_200_OK
                )
            
            # If no transactions, proceed with actual deletion
            instance.delete()
            
            logger.info(f"Account deleted successfully: {account_name}")
            
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

class AccountReportViewSet(viewsets.ViewSet):
    """
    Account reports using existing transaction models (Sales, Purchase, etc.)
    """
    
    def list(self, request, *args, **kwargs):
        """
        Get account summary report with actual transaction data
        """
        try:
            # Get query parameters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            account_id = request.query_params.get('account_id')
            company = request.user.company
            
            # Validate dates
            if start_date and end_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return custom_response(
                        success=False,
                        message="Invalid date format. Use YYYY-MM-DD.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # Base queryset for accounts
            accounts_queryset = Account.objects.filter(company=company, is_active=True)
            if account_id:
                accounts_queryset = accounts_queryset.filter(id=account_id)
            
            report_data = []
            
            for account in accounts_queryset:
                account_data = self._get_account_report(account, start_date, end_date)
                report_data.append(account_data)
            
            # Overall summary
            overall_summary = self._get_overall_summary(report_data, start_date, end_date)
            
            response_data = {
                'accounts': report_data,
                'overall_summary': overall_summary,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
            return custom_response(
                success=True,
                message="Account report fetched successfully.",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error generating account report: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_account_report(self, account, start_date, end_date):
        """
        Get detailed report for a single account using actual transaction models
        """
        # Initialize transaction filters
        date_filters = {}
        if start_date and end_date:
            date_filters = {'date__range': [start_date, end_date]}
        
        # Get transactions from different models
        # Sales transactions
        sales = Sale.objects.filter(account=account, **date_filters)
        sales_total = sales.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        
        # Purchase transactions
        purchases = Purchase.objects.filter(account=account, **date_filters)
        purchases_total = purchases.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        
        # Sales Return transactions
        sales_returns = SaleReturn.objects.filter(account=account, **date_filters)
        sales_returns_total = sales_returns.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        
        # Purchase Return transactions
        purchase_returns = PurchaseReturn.objects.filter(account=account, **date_filters)
        purchase_returns_total = purchase_returns.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        
        # Money Receipt transactions
        money_receipts = MoneyReceipt.objects.filter(account=account, **date_filters)
        money_receipts_total = money_receipts.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Supplier Payment transactions
        supplier_payments = SupplierPayment.objects.filter(account=account, **date_filters)
        supplier_payments_total = supplier_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Expense transactions (if you have Expense model)
        expenses_total = Decimal('0')
        try:
            expenses = Expense.objects.filter(account=account, **date_filters)
            expenses_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        except:
            pass  # Expense model might not exist
        
        # Calculate totals
        totals = {
            'sales': sales_total,
            'purchases': purchases_total,
            'sales_returns': sales_returns_total,
            'purchase_returns': purchase_returns_total,
            'money_receipts': money_receipts_total,
            'supplier_payments': supplier_payments_total,
            'expenses': expenses_total,
            'net_flow': Decimal('0')
        }
        
        # Calculate net cash flow
        # Inflows: sales, money_receipts, purchase_returns
        inflows = totals['sales'] + totals['money_receipts'] + totals['purchase_returns']
        
        # Outflows: purchases, supplier_payments, sales_returns, expenses
        outflows = totals['purchases'] + totals['supplier_payments'] + totals['sales_returns'] + totals['expenses']
        
        totals['net_flow'] = inflows - outflows
        
        # Get transaction details from all models
        transaction_details = []
        
        # Sales transactions
        for sale in sales:
            transaction_details.append({
                'id': sale.id,
                'transaction_id': sale.invoice_no,
                'transaction_type': 'sale',
                'transaction_type_display': 'Sale',
                'date': sale.date,
                'amount': float(sale.grand_total),
                'reference_number': sale.invoice_no,
                'description': f"Sale - {sale.customer.name if sale.customer else 'Walk-in Customer'}",
                'customer': sale.customer.name if sale.customer else 'Walk-in Customer',
                'supplier': None,
                'status': 'completed'
            })
        
        # Purchase transactions
        for purchase in purchases:
            transaction_details.append({
                'id': purchase.id,
                'transaction_id': purchase.invoice_no,
                'transaction_type': 'purchase',
                'transaction_type_display': 'Purchase',
                'date': purchase.date,
                'amount': float(purchase.grand_total),
                'reference_number': purchase.invoice_no,
                'description': f"Purchase - {purchase.supplier.name if purchase.supplier else 'Supplier'}",
                'customer': None,
                'supplier': purchase.supplier.name if purchase.supplier else 'Supplier',
                'status': 'completed'
            })
        
        # Sales Return transactions
        for sale_return in sales_returns:
            transaction_details.append({
                'id': sale_return.id,
                'transaction_id': sale_return.return_no,
                'transaction_type': 'sales_return',
                'transaction_type_display': 'Sales Return',
                'date': sale_return.date,
                'amount': float(sale_return.grand_total),
                'reference_number': sale_return.return_no,
                'description': f"Sales Return - {sale_return.customer.name if sale_return.customer else 'Customer'}",
                'customer': sale_return.customer.name if sale_return.customer else 'Customer',
                'supplier': None,
                'status': 'completed'
            })
        
        # Purchase Return transactions
        for purchase_return in purchase_returns:
            transaction_details.append({
                'id': purchase_return.id,
                'transaction_id': purchase_return.return_no,
                'transaction_type': 'purchase_return',
                'transaction_type_display': 'Purchase Return',
                'date': purchase_return.date,
                'amount': float(purchase_return.grand_total),
                'reference_number': purchase_return.return_no,
                'description': f"Purchase Return - {purchase_return.supplier.name if purchase_return.supplier else 'Supplier'}",
                'customer': None,
                'supplier': purchase_return.supplier.name if purchase_return.supplier else 'Supplier',
                'status': 'completed'
            })
        
        # Money Receipt transactions
        for receipt in money_receipts:
            transaction_details.append({
                'id': receipt.id,
                'transaction_id': receipt.receipt_no,
                'transaction_type': 'money_receipt',
                'transaction_type_display': 'Money Receipt',
                'date': receipt.date,
                'amount': float(receipt.amount),
                'reference_number': receipt.receipt_no,
                'description': f"Money Receipt - {receipt.customer.name if receipt.customer else 'Customer'}",
                'customer': receipt.customer.name if receipt.customer else 'Customer',
                'supplier': None,
                'status': 'completed'
            })
        
        # Supplier Payment transactions
        for payment in supplier_payments:
            transaction_details.append({
                'id': payment.id,
                'transaction_id': payment.payment_no,
                'transaction_type': 'supplier_payment',
                'transaction_type_display': 'Supplier Payment',
                'date': payment.date,
                'amount': float(payment.amount),
                'reference_number': payment.payment_no,
                'description': f"Supplier Payment - {payment.supplier.name if payment.supplier else 'Supplier'}",
                'customer': None,
                'supplier': payment.supplier.name if payment.supplier else 'Supplier',
                'status': 'completed'
            })
        
        # Expense transactions (if exists)
        try:
            for expense in Expense.objects.filter(account=account, **date_filters):
                transaction_details.append({
                    'id': expense.id,
                    'transaction_id': expense.expense_no,
                    'transaction_type': 'expense',
                    'transaction_type_display': 'Expense',
                    'date': expense.date,
                    'amount': float(expense.amount),
                    'reference_number': expense.expense_no,
                    'description': f"Expense - {expense.category if hasattr(expense, 'category') else 'General'}",
                    'customer': None,
                    'supplier': None,
                    'status': 'completed'
                })
        except:
            pass
        
        # Sort transactions by date
        transaction_details.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate total transaction count
        total_transactions = (
            sales.count() + purchases.count() + sales_returns.count() + 
            purchase_returns.count() + money_receipts.count() + 
            supplier_payments.count()
        )
        
        return {
            'account': {
                'id': account.id,
                'name': account.name,
                'number': account.number,
                'ac_type': account.ac_type,
                'ac_type_display': account.get_ac_type_display(),
                'balance': float(account.balance),
                'bank_name': account.bank_name,
                'branch': account.branch
            },
            'totals': {key: float(value) for key, value in totals.items()},
            'transaction_count': total_transactions,
            'transactions': transaction_details
        }
    
    def _get_overall_summary(self, account_reports, start_date, end_date):
        """
        Calculate overall summary across all accounts
        """
        overall_totals = {
            'total_sales': Decimal('0'),
            'total_purchases': Decimal('0'),
            'total_sales_returns': Decimal('0'),
            'total_purchase_returns': Decimal('0'),
            'total_money_receipts': Decimal('0'),
            'total_supplier_payments': Decimal('0'),
            'total_expenses': Decimal('0'),
            'total_inflows': Decimal('0'),
            'total_outflows': Decimal('0'),
            'net_cash_flow': Decimal('0'),
            'total_accounts': len(account_reports),
            'total_transactions': 0
        }
        
        for report in account_reports:
            totals = report['totals']
            overall_totals['total_sales'] += Decimal(str(totals['sales']))
            overall_totals['total_purchases'] += Decimal(str(totals['purchases']))
            overall_totals['total_sales_returns'] += Decimal(str(totals['sales_returns']))
            overall_totals['total_purchase_returns'] += Decimal(str(totals['purchase_returns']))
            overall_totals['total_money_receipts'] += Decimal(str(totals['money_receipts']))
            overall_totals['total_supplier_payments'] += Decimal(str(totals['supplier_payments']))
            overall_totals['total_expenses'] += Decimal(str(totals['expenses']))
            overall_totals['total_transactions'] += report['transaction_count']
        
        # Calculate inflows and outflows
        overall_totals['total_inflows'] = (
            overall_totals['total_sales'] + 
            overall_totals['total_money_receipts'] + 
            overall_totals['total_purchase_returns']
        )
        
        overall_totals['total_outflows'] = (
            overall_totals['total_purchases'] + 
            overall_totals['total_supplier_payments'] + 
            overall_totals['total_sales_returns'] + 
            overall_totals['total_expenses']
        )
        
        overall_totals['net_cash_flow'] = (
            overall_totals['total_inflows'] - 
            overall_totals['total_outflows']
        )
        
        # Convert to float for JSON serialization
        return {key: float(value) for key, value in overall_totals.items()}
    
    @action(detail=False, methods=['get'])
    def transaction_summary(self, request):
        """
        Get transaction summary by type for all accounts
        """
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            company = request.user.company
            
            # Build date filters
            date_filters = {}
            if start_date and end_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    date_filters = {'date__range': [start_date, end_date]}
                except ValueError:
                    return custom_response(
                        success=False,
                        message="Invalid date format. Use YYYY-MM-DD.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # Get transaction summary by type from actual models
            transaction_summary = []
            
            # Sales
            sales_total = Sale.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('grand_total'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'sale',
                'total_amount': float(sales_total['total_amount'] or 0),
                'transaction_count': sales_total['count'] or 0
            })
            
            # Purchases
            purchases_total = Purchase.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('grand_total'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'purchase',
                'total_amount': float(purchases_total['total_amount'] or 0),
                'transaction_count': purchases_total['count'] or 0
            })
            
            # Sales Returns
            sales_returns_total = SaleReturn.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('grand_total'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'sales_return',
                'total_amount': float(sales_returns_total['total_amount'] or 0),
                'transaction_count': sales_returns_total['count'] or 0
            })
            
            # Purchase Returns
            purchase_returns_total = PurchaseReturn.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('grand_total'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'purchase_return',
                'total_amount': float(purchase_returns_total['total_amount'] or 0),
                'transaction_count': purchase_returns_total['count'] or 0
            })
            
            # Money Receipts
            money_receipts_total = MoneyReceipt.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'money_receipt',
                'total_amount': float(money_receipts_total['total_amount'] or 0),
                'transaction_count': money_receipts_total['count'] or 0
            })
            
            # Supplier Payments
            supplier_payments_total = SupplierPayment.objects.filter(company=company, **date_filters).aggregate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            transaction_summary.append({
                'transaction_type': 'supplier_payment',
                'total_amount': float(supplier_payments_total['total_amount'] or 0),
                'transaction_count': supplier_payments_total['count'] or 0
            })
            
            response_data = {
                'transaction_summary': transaction_summary,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
            return custom_response(
                success=True,
                message="Transaction summary fetched successfully.",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error generating transaction summary: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )