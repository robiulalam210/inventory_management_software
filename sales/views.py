from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.utils import custom_response
from core.base_viewsets import BaseCompanyViewSet
from .models import Sale, SaleItem
from .serializers import SaleSerializer, SaleItemSerializer, DueSaleSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from django.db import models
import logging
from customers.models import Customer

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
# -----------------------------
class SaleViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    # List all sales
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page else queryset, many=True)
            return custom_response(
                success=True,
                message="Sales fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching sales: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Create a new sale
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            sale = serializer.save(company=request.user.company)
            return custom_response(
                success=True,
                message="Sale created successfully.",
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
                message=f"Failed to create sale: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -----------------------------
# SaleItem ViewSet
# -----------------------------
class SaleItemViewSet(BaseCompanyViewSet):
    queryset = SaleItem.objects.all().select_related('sale', 'product')
    serializer_class = SaleItemSerializer
    permission_classes = [IsAuthenticated]
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