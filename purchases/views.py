from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.db.models import Q
import logging
from core.utils import custom_response
from core.base_viewsets import BaseCompanyViewSet
from core.pagination import CustomPageNumberPagination
from .models import Purchase, PurchaseItem
from .serializers import PurchaseSerializer, PurchaseItemSerializer
from suppliers.models import Supplier

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_due_purchases(request, supplier_id=None):
    """
    Get due purchases for a Supplier
    
    URL patterns:
    - /api/purchase-due/?supplier_id=3
    - /api/purchase-due/3/
    """
    logger.info("Due purchases API called", extra={
        'user': request.user.id,
        'supplier_id': supplier_id,
        'query_params': dict(request.GET)
    })

    # Get supplier_id from URL parameter or query parameter
    supplier_id = supplier_id or request.GET.get('supplier_id')
    due_only = request.GET.get('due', 'true').lower() == 'true'

    if not supplier_id:
        logger.warning("No supplier_id provided")
        return Response({
            "status": False,
            "message": "Supplier ID is required. Use /api/purchase-due/3/ or /api/purchase-due/?supplier_id=3",
            "data": []
        }, status=400)
    
    try:
        # Convert to integer if it's string
        if isinstance(supplier_id, str):
            supplier_id = int(supplier_id)

        # Check if supplier exists
        supplier = Supplier.objects.get(id=supplier_id)
        logger.info(f"Supplier found: {supplier.name} (ID: {supplier.id})")

        # Filter purchases by supplier AND company (multi-tenant)
        queryset = Purchase.objects.filter(
            supplier_id=supplier_id,
            company=request.user.company
        )
        
        # If due_only is true, filter only purchases with due amount > 0
        if due_only:
            queryset = queryset.filter(due_amount__gt=0)
        
        # Order by purchase date (oldest first)
        queryset = queryset.order_by('purchase_date')
        
        # Use serializer for consistent data format
        serializer = PurchaseSerializer(queryset, many=True)
        
        logger.info(f"Found {queryset.count()} due purchases for supplier {supplier_id}")
        
        return Response({
            "status": True,
            "message": f"Found {queryset.count()} due purchases for {supplier.name}",
            "data": serializer.data
        })
        
    except ValueError:
        logger.error(f"Invalid supplier_id format: {supplier_id}")
        return Response({
            "status": False,
            "message": "Invalid supplier ID format",
            "data": []
        }, status=400)
    except Supplier.DoesNotExist:
        logger.error(f"Supplier not found with ID: {supplier_id}")
        return Response({
            "status": False,
            "message": f"Supplier with ID {supplier_id} not found",
            "data": []
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_due_purchases: {str(e)}", exc_info=True)
        return Response({
            "status": False,
            "message": f"Error fetching due purchases: {str(e)}",
            "data": []
        }, status=500)


class PurchaseViewSet(BaseCompanyViewSet):
    queryset = Purchase.objects.all().select_related('supplier', 'account')
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        """Apply filters to queryset"""
        queryset = super().get_queryset()
        
        # Get filter parameters
        payment_status = self.request.query_params.get('payment_status')
        supplier_id = self.request.query_params.get('supplier_id')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        invoice_no = self.request.query_params.get('invoice_no')
        
        # Apply filters
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
            
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
            
        if start_date and end_date:
            queryset = queryset.filter(purchase_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(purchase_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(purchase_date__lte=end_date)
            
        if invoice_no:
            queryset = queryset.filter(invoice_no__icontains=invoice_no)
            
        return queryset.order_by('-purchase_date', '-id')

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
                message="Purchases fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in purchase list: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Purchase details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in purchase retrieve: {str(e)}", exc_info=True)
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
            instance = serializer.save()
            return custom_response(
                success=True,
                message="Purchase created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            logger.warning(f"Purchase validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error.",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in purchase create: {str(e)}", exc_info=True)
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
            instance = serializer.save()
            return custom_response(
                success=True,
                message="Purchase updated successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            logger.warning(f"Purchase update validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error.",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in purchase update: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get purchase summary statistics"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            total_purchases = queryset.count()
            total_amount = queryset.aggregate(total=models.Sum('grand_total'))['total'] or 0
            total_due = queryset.aggregate(total=models.Sum('due_amount'))['total'] or 0
            total_paid = queryset.aggregate(total=models.Sum('paid_amount'))['total'] or 0
            
            # Count by payment status
            status_count = queryset.values('payment_status').annotate(
                count=models.Count('id')
            )
            
            summary_data = {
                'total_purchases': total_purchases,
                'total_amount': float(total_amount),
                'total_due': float(total_due),
                'total_paid': float(total_paid),
                'payment_status_breakdown': list(status_count)
            }
            
            return custom_response(
                success=True,
                message="Purchase summary fetched successfully.",
                data=summary_data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in purchase summary: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PurchaseItemViewSet(BaseCompanyViewSet):
    queryset = PurchaseItem.objects.all().select_related('purchase', 'product')
    serializer_class = PurchaseItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    company_field = 'purchase__company'

    def get_queryset(self):
        """Apply filters to purchase items queryset"""
        queryset = super().get_queryset()
        
        purchase_id = self.request.query_params.get('purchase_id')
        product_id = self.request.query_params.get('product_id')
        
        if purchase_id:
            queryset = queryset.filter(purchase_id=purchase_id)
            
        if product_id:
            queryset = queryset.filter(product_id=product_id)
            
        return queryset.order_by('-purchase__purchase_date', 'id')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Purchase items fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in purchase item list: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Purchase item details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error in purchase item retrieve: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )