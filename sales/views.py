from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.db import models
from django.db.models import Q, F, Sum, Value, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from core.utils import custom_response
from core.pagination import CustomPageNumberPagination    
from core.base_viewsets import BaseCompanyViewSet
from sales.models import Sale, SaleItem
from .serializers import SaleSerializer, SaleItemSerializer, DueSaleSerializer
from customers.models import Customer
from accounts.models import Account

logger = logging.getLogger(__name__)

# -----------------------------
# Due Sales API View
# -----------------------------
@api_view(['GET'])
def get_due_sales(request):
    """
    Get due sales for a customer
    URL: /api/sales/due/?customer_id=1&due=true
    """
    customer_id = request.GET.get('customer_id')
    due_only = request.GET.get('due', 'true').lower() == 'true'
    
    if not customer_id:
        return Response({
            "status": False,
            "message": "Customer ID is required",
            "data": []
        }, status=400)
    
    try:
        # Check if customer exists
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({
                "status": False,
                "message": f"Customer with ID {customer_id} not found",
                "data": []
            }, status=404)

        # Filter sales by customer AND company (multi-tenant)
        queryset = Sale.objects.filter(
            customer_id=customer_id,
            company=request.user.company
        )
        
        # If due_only is true, filter only sales with due amount > 0
        if due_only:
            queryset = queryset.filter(payable_amount__gt=models.F('paid_amount'))
        
        # Order by sale date (oldest first)
        queryset = queryset.order_by('sale_date')
        
        serializer = DueSaleSerializer(queryset, many=True)
        
        return Response({
            "status": True,
            "message": f"Found {queryset.count()} due sales for {customer.name}",
            "data": serializer.data
        })
        
    except Exception as e:
        logger.error(f"ERROR in get_due_sales: {str(e)}")
        return Response({
            "status": False,
            "message": f"Error fetching due sales: {str(e)}",
            "data": []
        }, status=500)

# -----------------------------
# Sale Payment API
# -----------------------------
class SalePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, sale_id):
        """
        Add payment to existing sale
        POST /api/sales/{sale_id}/add-payment/
        {
            "amount": 100.00,
            "payment_method": "Cash",
            "account_id": 12,
            "create_receipt": true
        }
        """
        try:
            sale = Sale.objects.get(id=sale_id, company=request.user.company)
            
            amount = Decimal(request.data.get('amount', 0))
            payment_method = request.data.get('payment_method')
            account_id = request.data.get('account_id')
            create_receipt = request.data.get('create_receipt', True)
            
            if amount <= 0:
                return Response({
                    "status": False,
                    "message": "Payment amount must be greater than 0"
                }, status=400)
            
            # Get account if provided
            account = None
            if account_id:
                try:
                    account = Account.objects.get(id=account_id, company=request.user.company)
                except Account.DoesNotExist:
                    return Response({
                        "status": False,
                        "message": "Account not found"
                    }, status=404)
            
            # Add payment using the model method
            new_paid_amount = sale.add_payment(
                amount=amount,
                payment_method=payment_method,
                account=account
            )
            
            # Create money receipt if requested
            if create_receipt and sale.with_money_receipt == 'Yes':
                sale.create_money_receipt()
            
            # Refresh sale data
            sale.refresh_from_db()
            
            return Response({
                "status": True,
                "message": f"Payment of {amount} added successfully",
                "data": {
                    "sale_id": sale.id,
                    "invoice_no": sale.invoice_no,
                    "paid_amount": float(sale.paid_amount),
                    "due_amount": float(sale.due_amount),
                    "payment_status": sale.payment_status,
                    "remaining_balance": float(max(0, sale.payable_amount - sale.paid_amount))
                }
            })
            
        except Sale.DoesNotExist:
            return Response({
                "status": False,
                "message": "Sale not found"
            }, status=404)
        except Exception as e:
            return Response({
                "status": False,
                "message": f"Error adding payment: {str(e)}"
            }, status=400)

# -----------------------------
# Sale ViewSet
# -----------------------------
class SaleViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        return queryset

    def apply_filters(self, queryset):
        """
        Apply comprehensive filtering to sales queryset
        """
        params = self.request.GET
        
        # Customer filter
        customer_id = params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Seller filter
        seller_id = params.get('seller')
        if seller_id:
            queryset = queryset.filter(sale_by_id=seller_id)

        # Date range filters
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if start_date and end_date:
            try:
                # Handle both full ISO string and date-only formats
                if 'T' in start_date:
                    start = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
                else:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    
                if 'T' in end_date:
                    end = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
                else:
                    end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                queryset = queryset.filter(sale_date__range=[start, end])
            except ValueError as e:
                logger.error(f"Invalid date format: {e}")
        
        # Search filter
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_no__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(customer__phone__icontains=search)
            )
        
        # Due only filter
        due_only = params.get('due_only')
        if due_only and due_only.lower() == 'true':
            queryset = queryset.filter(payable_amount__gt=models.F('paid_amount'))
        
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Enhanced list method with filtering support
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} sales",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error in sales list: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching sales: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Custom actions
    @action(detail=False, methods=['get'])
    def due_sales(self, request):
        """
        Get all due sales (alias for due_only=true filter)
        """
        self.request.GET = self.request.GET.copy()
        self.request.GET['due_only'] = 'true'
        return self.list(request)

    @action(detail=False, methods=['get'])
    def today_sales(self, request):
        """
        Get today's sales
        """
        self.request.GET = self.request.GET.copy()
        today = timezone.now().date()
        self.request.GET['start_date'] = today.isoformat()
        self.request.GET['end_date'] = today.isoformat()
        return self.list(request)

# -----------------------------
# SaleItem ViewSet
# -----------------------------
class SaleItemViewSet(BaseCompanyViewSet):
    queryset = SaleItem.objects.all().select_related('sale', 'product')
    serializer_class = SaleItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    company_field = 'sale__company'

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page else queryset, many=True)
            return custom_response(
                success=True,
                message="Sale items fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching sale items: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -----------------------------
# SaleAllListViewSet
# -----------------------------
class SaleAllListViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        return queryset

    def apply_filters(self, queryset):
        """
        Apply comprehensive filtering to sales queryset
        """
        params = self.request.GET

        # Customer filter
        customer_id = params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Seller filter
        seller_id = params.get('seller')
        if seller_id:
            queryset = queryset.filter(sale_by_id=seller_id)

        # Date range filter
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date or end_date:
            try:
                def parse_date(date_str):
                    if not date_str:
                        return None
                    if 'T' in date_str:
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                    return datetime.strptime(date_str, '%Y-%m-%d').date()

                start = parse_date(start_date)
                end = parse_date(end_date)

                if start and end:
                    queryset = queryset.filter(sale_date__range=[start, end])
                elif start:
                    queryset = queryset.filter(sale_date__gte=start)
                elif end:
                    queryset = queryset.filter(sale_date__lte=end)

            except ValueError as e:
                logger.error(f"Invalid date format: {e}")

        # Search filter
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_no__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(customer__phone__icontains=search)
            )

        # Due-only filter
        due_only = params.get('due_only')
        if due_only and due_only.lower() == 'true':
            queryset = queryset.filter(payable_amount__gt=F('paid_amount'))

        return queryset

    def list(self, request, *args, **kwargs):
        """Enhanced list method with filtering"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
        
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} sales",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error in sales list: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching sales: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )