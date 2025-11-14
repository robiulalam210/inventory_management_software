from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Transaction
from accounts.models import Account
from .serializers import (
    TransactionSerializer, 
    TransactionCreateSerializer,
    AccountBalanceSerializer,
    TransactionSummarySerializer
)
import logging

logger = logging.getLogger(__name__)

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transaction_no', 'description', 'account__name']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    ordering = ['-transaction_date']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        initial_count = queryset.count()
        logger.info(f"🔍 Initial transaction count: {initial_count}")
        
        company_id = self.request.query_params.get('company_id')
        
        # Filter by company if provided
        if company_id:
            before_company_count = queryset.count()
            queryset = queryset.filter(company_id=company_id)
            after_company_count = queryset.count()
            logger.info(f"🔍 After company filter ({company_id}): {before_company_count} -> {after_company_count}")
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                before_date_count = queryset.count()
                queryset = queryset.filter(transaction_date__range=[start_date, end_date])
                after_date_count = queryset.count()
                logger.info(f"🔍 After date range filter: {before_date_count} -> {after_date_count}")
            except ValueError:
                pass
        elif start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                before_date_count = queryset.count()
                queryset = queryset.filter(transaction_date__gte=start_date)
                after_date_count = queryset.count()
                logger.info(f"🔍 After start date filter: {before_date_count} -> {after_date_count}")
            except ValueError:
                pass
        elif end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                before_date_count = queryset.count()
                queryset = queryset.filter(transaction_date__lte=end_date)
                after_date_count = queryset.count()
                logger.info(f"🔍 After end date filter: {before_date_count} -> {after_date_count}")
            except ValueError:
                pass
        
        # Filter by account
        account_id = self.request.query_params.get('account_id')
        if account_id:
            before_account_count = queryset.count()
            queryset = queryset.filter(account_id=account_id)
            after_account_count = queryset.count()
            logger.info(f"🔍 After account filter ({account_id}): {before_account_count} -> {after_account_count}")
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type:
            before_type_count = queryset.count()
            queryset = queryset.filter(transaction_type=transaction_type)
            after_type_count = queryset.count()
            logger.info(f"🔍 After transaction type filter ({transaction_type}): {before_type_count} -> {after_type_count}")
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            before_status_count = queryset.count()
            queryset = queryset.filter(status=status_filter)
            after_status_count = queryset.count()
            logger.info(f"🔍 After status filter ({status_filter}): {before_status_count} -> {after_status_count}")
        
        final_count = queryset.count()
        logger.info(f"🔍 Final transaction count: {final_count}")
        logger.info(f"🔍 Missing transactions: {initial_count - final_count}")
        
        # Use select_related but don't let it filter out transactions
        try:
            queryset = queryset.select_related(
                'account', 'created_by', 'sale', 'money_receipt', 
                'expense', 'purchase', 'supplier_payment', 'company'
            )
        except Exception as e:
            logger.warning(f"⚠️ Select related failed: {e}, using basic queryset")
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TransactionCreateSerializer
        return TransactionSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """Reverse a transaction"""
        transaction = self.get_object()
        
        try:
            reversal = transaction.reverse_transaction()
            reversal_serializer = self.get_serializer(reversal)
            return Response({
                'message': 'Transaction reversed successfully',
                'reversal_transaction': reversal_serializer.data
            })
        except Exception as e:
            logger.error(f"Error reversing transaction {pk}: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def debug_missing(self, request):
        """Debug endpoint to find missing transactions"""
        # Get all transaction IDs from database
        all_transactions = Transaction.objects.all()
        all_ids = set(all_transactions.values_list('id', flat=True))
        
        # Get filtered transaction IDs
        filtered_queryset = self.get_queryset()
        filtered_ids = set(filtered_queryset.values_list('id', flat=True))
        
        # Find missing IDs
        missing_ids = all_ids - filtered_ids
        
        # Get details of missing transactions
        missing_transactions = all_transactions.filter(id__in=missing_ids).values(
            'id', 'transaction_no', 'company_id', 'status', 
            'transaction_type', 'transaction_date', 'amount'
        )
        
        # Get query parameters
        query_params = {
            'company_id': request.query_params.get('company_id'),
            'start_date': request.query_params.get('start_date'),
            'end_date': request.query_params.get('end_date'),
            'account_id': request.query_params.get('account_id'),
            'transaction_type': request.query_params.get('transaction_type'),
            'status': request.query_params.get('status'),
        }
        
        return Response({
            'database_total': all_transactions.count(),
            'api_total': filtered_queryset.count(),
            'missing_count': len(missing_ids),
            'query_parameters': query_params,
            'missing_transactions': list(missing_transactions),
            'breakdown': {
                'by_company': list(all_transactions.values('company_id').annotate(count=Count('id'))),
                'by_status': list(all_transactions.values('status').annotate(count=Count('id'))),
                'by_type': list(all_transactions.values('transaction_type').annotate(count=Count('id'))),
            }
        })
    
    @action(detail=False, methods=['get'])
    def unfiltered(self, request):
        """Get all transactions without any filters"""
        transactions = Transaction.objects.all().select_related(
            'account', 'created_by', 'company'
        )
        serializer = self.get_serializer(transactions, many=True)
        return Response({
            'total_count': transactions.count(),
            'transactions': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def account_balances(self, request):
        """Get account balances with transaction summaries"""
        company_id = request.query_params.get('company_id')
        
        if not company_id:
            return Response(
                {'error': 'company_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        accounts = Account.objects.filter(company_id=company_id, is_active=True)
        
        # Annotate with transaction totals
        accounts = accounts.annotate(
            total_credits=Sum(
                'transactions__amount',
                filter=Q(transactions__transaction_type='credit', 
                        transactions__status='completed')
            ),
            total_debits=Sum(
                'transactions__amount',
                filter=Q(transactions__transaction_type='debit', 
                        transactions__status='completed')
            ),
            transaction_count=Count(
                'transactions',
                filter=Q(transactions__status='completed')
            )
        )
        
        for account in accounts:
            account.current_balance = (account.total_credits or 0) - (account.total_debits or 0)
        
        serializer = AccountBalanceSerializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary for dashboard"""
        company_id = request.query_params.get('company_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not company_id:
            return Response(
                {'error': 'company_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build base queryset
        transactions = Transaction.objects.filter(
            company_id=company_id,
            status='completed'
        )
        
        # Apply date filters
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                transactions = transactions.filter(transaction_date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                transactions = transactions.filter(transaction_date__lte=end_date)
            except ValueError:
                pass
        
        # Calculate totals
        total_transactions = transactions.count()
        total_credits = transactions.filter(transaction_type='credit').aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_debits = transactions.filter(transaction_type='debit').aggregate(
            total=Sum('amount')
        )['total'] or 0
        net_flow = total_credits - total_debits
        
        summary_data = {
            'total_transactions': total_transactions,
            'total_credits': float(total_credits),
            'total_debits': float(total_debits),
            'net_flow': float(net_flow)
        }
        
        serializer = TransactionSummarySerializer(summary_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def daily_summary(self, request):
        """Get today's and this month's transaction summary"""
        company_id = request.query_params.get('company_id')
        
        if not company_id:
            return Response(
                {'error': 'company_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Today's transactions
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        today_transactions = Transaction.objects.filter(
            company_id=company_id,
            transaction_date__range=[today_start, today_end],
            status='completed'
        )
        
        # This month's transactions
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month_start.replace(month=month_start.month+1) if month_start.month < 12 else month_start.replace(year=month_start.year+1, month=1)
        
        month_transactions = Transaction.objects.filter(
            company_id=company_id,
            transaction_date__range=[month_start, next_month],
            status='completed'
        )
        
        summary = {
            'today': {
                'total_transactions': today_transactions.count(),
                'total_credits': float(today_transactions.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0),
                'total_debits': float(today_transactions.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0),
            },
            'this_month': {
                'total_transactions': month_transactions.count(),
                'total_credits': float(month_transactions.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0),
                'total_debits': float(month_transactions.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0),
            }
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def by_account(self, request):
        """Get transactions for a specific account"""
        account_id = request.query_params.get('account_id')
        if not account_id:
            return Response(
                {'error': 'account_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            account = Account.objects.get(id=account_id)
            transactions = Transaction.objects.filter(account=account).order_by('-transaction_date')
            serializer = self.get_serializer(transactions, many=True)
            return Response(serializer.data)
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent transactions (last 50)"""
        company_id = request.query_params.get('company_id')
        
        if not company_id:
            return Response(
                {'error': 'company_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transactions = Transaction.objects.filter(
            company_id=company_id,
            status='completed'
        ).order_by('-transaction_date')[:50]
        
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)