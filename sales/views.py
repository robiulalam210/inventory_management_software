from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination    
from core.base_viewsets import BaseCompanyViewSet
from sales.models import Sale, SaleItem
from .serializers import SaleSerializer, SaleItemSerializer, DueSaleSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import models
import logging
from customers.models import Customer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, F, Sum, Value, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# -----------------------------
# Due Sales API View - STANDALONE FUNCTION
# -----------------------------
@api_view(['GET'])
def get_due_sales(request):
    """
    Get due sales for a customer
    URL: /api/sales/due/?customer_id=1&due=true
    """
    customer_id = request.GET.get('customer_id')
    due_only = request.GET.get('due', 'true').lower() == 'true'
    
    print("=" * 50)
    print("🔄 DUE SALES API CALLED")
    print(f"📝 Customer ID: {customer_id}")
    print(f"📝 Due Only: {due_only}")
    print(f"📝 All GET params: {dict(request.GET)}")
    print("=" * 50)

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
            print(f"✅ Customer found: {customer.name} (ID: {customer.id})")
        except Customer.DoesNotExist:
            print(f"❌ Customer not found with ID: {customer_id}")
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
        print(f"📊 Total sales for customer: {queryset.count()}")
        
        # If due_only is true, filter only sales with due amount > 0
        if due_only:
            queryset = queryset.filter(payable_amount__gt=models.F('paid_amount'))
            print(f"📊 Due sales (payable_amount > paid_amount): {queryset.count()}")
        
        # Order by sale date (oldest first)
        queryset = queryset.order_by('sale_date')
        
        # Print each sale for detailed debugging
        print("📋 Sales Details:")
        for sale in queryset:
            due_amount = max(0, sale.payable_amount - sale.paid_amount)
            print(f"   🧾 Invoice: {sale.invoice_no}")
            print(f"      💰 Grand Total: {sale.grand_total}")
            print(f"      💵 Paid Amount: {sale.paid_amount}") 
            print(f"      🏦 Due Amount: {due_amount}")
            print(f"      📅 Date: {sale.sale_date}")
            print(f"      🔄 Payment Status: {sale.payment_status}")
            print(f"      👤 Customer: {sale.customer.name if sale.customer else 'None'}")
            print("   " + "-" * 30)
        
        serializer = DueSaleSerializer(queryset, many=True)
        
        print(f"✅ API Response: {queryset.count()} due sales found")
        print("=" * 50)
        
        return Response({
            "status": True,
            "message": f"Found {queryset.count()} due sales for {customer.name}",
            "data": serializer.data
        })
        
    except Exception as e:
        print(f"❌ ERROR in get_due_sales: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response({
            "status": False,
            "message": f"Error fetching due sales: {str(e)}",
            "data": []
        }, status=500)

# -----------------------------
# Sale ViewSet

class SaleViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters based on query parameters
        queryset = self.apply_filters(queryset)
        
        return queryset

    def apply_filters(self, queryset):
        """
        Apply comprehensive filtering to sales queryset
        """
        params = self.request.GET
        
        print("🔄 APPLYING FILTERS")
        print(f"📝 All GET params: {dict(params)}")
        
        # Customer filter
        customer_id = params.get('customer')
        if customer_id:
            print(f"🔍 Filtering by customer ID: {customer_id}")
            queryset = queryset.filter(customer_id=customer_id)
        

          # SALER filter
     # SALE_BY filter
       # SALE_BY (Seller) filter
        seller_id = params.get('seller')

        if seller_id:
            print(f"🔍 Filtering by seller (user) ID: {seller_id}")
            queryset = queryset.filter(sale_by_id=seller_id)


        # Date range filters - FIXED date parsing
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
                print(f"📅 Filtered by date range: {start} to {end}")
            except ValueError as e:
                print(f"❌ Invalid date format: {e}")
                print(f"❌ Start date: {start_date}, End date: {end_date}")
        
        # Search filter
        search = params.get('search')
        if search:
            print(f"🔍 Applying search filter: {search}")
            queryset = queryset.filter(
                Q(invoice_no__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(customer__phone__icontains=search)
            )
        
        # Due only filter
        due_only = params.get('due_only')
        if due_only and due_only.lower() == 'true':
            print(f"🔍 Filtering due sales only")
            queryset = queryset.filter(payable_amount__gt=models.F('paid_amount'))
        
        print(f"✅ Final queryset count: {queryset.count()}")
        
        # Debug: Print first few results to verify filtering
        if queryset.count() > 0:
            print("📋 Sample filtered results:")
            for sale in queryset[:3]:
                print(f"   - Invoice: {sale.invoice_no}, Customer: {sale.customer.name if sale.customer else 'None'}")
        
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Enhanced list method with filtering support
        """
        try:
            # Log filter parameters for debugging
            logger.info(f"Sales list called with filters: {dict(request.GET)}")
            
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            
            # Add filter summary to response
            response_data = {
                'data': serializer.data,
                'filters_applied': self.get_applied_filters_info(),
                'summary': self.get_sales_summary(queryset)
            }
            
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} sales",
                data=response_data,
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

    def get_applied_filters_info(self):
        """
        Return information about applied filters
        """
        params = self.request.GET
        applied_filters = {}
        
        filter_mapping = {
            'start_date': 'Date From',
            'end_date': 'Date To', 
            'customer': 'Customer',
            'invoice_no': 'Invoice Number',
            'payment_status': 'Payment Status',
            'payment_method': 'Payment Method',
            'min_amount': 'Minimum Amount',
            'max_amount': 'Maximum Amount',
            'due_only': 'Due Sales Only',
            'paid_only': 'Paid Sales Only',
            'partial_payment': 'Partial Payments',
            'search': 'Search Term'
        }
        
        for param, display_name in filter_mapping.items():
            value = params.get(param)
            if value:
                applied_filters[display_name] = value
        
        return applied_filters

    def get_sales_summary(self, queryset):
        """
        Get summary statistics for the filtered sales
        """
        try:
            summary = queryset.aggregate(
                total_sales=Count('id'),
                total_amount=Coalesce(Sum('grand_total'), Value(0)),
                total_paid=Coalesce(Sum('paid_amount'), Value(0)),
                total_due=Coalesce(Sum('payable_amount') - Sum('paid_amount'), Value(0))
            )
            
            return {
                'total_sales': summary['total_sales'],
                'total_amount': float(summary['total_amount']),
                'total_paid': float(summary['total_paid']),
                'total_due': float(summary['total_due'])
            }
        except Exception as e:
            logger.error(f"Error calculating sales summary: {str(e)}")
            return {}

    # Custom actions for common filter scenarios
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

    @action(detail=False, methods=['get'])
    def recent_sales(self, request):
        """
        Get sales from last 7 days
        """
        queryset = self.filter_queryset(self.get_queryset())
        last_week = timezone.now().date() - timedelta(days=7)
        recent_sales = queryset.filter(sale_date__gte=last_week)
        
        page = self.paginate_queryset(recent_sales)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(recent_sales, many=True)
        return custom_response(
            success=True,
            message=f"Found {recent_sales.count()} recent sales",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )


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

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            sale_item = serializer.save()
            return custom_response(
                success=True,
                message="Sale item created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            # ✅ FIXED: Corrected syntax errors
            if isinstance(e.detail, list) and len(e.detail) > 0:
                error_message = e.detail[0]
            elif isinstance(e.detail, dict) and e.detail:
                first_key = list(e.detail.keys())[0]
                first_error = e.detail[first_key]
                error_message = first_error[0] if isinstance(first_error, list) else first_error
            else:
                error_message = str(e.detail) if e.detail else "Validation Error"
            
            return custom_response(
                success=False,
                message=error_message,
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Failed to create sale item: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )