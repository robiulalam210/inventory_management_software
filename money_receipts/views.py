from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .serializers import MoneyReceiptSerializer
from .models import MoneyReceipt
import logging

logger = logging.getLogger(__name__)

class MoneyReceiptCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Base queryset with company filtering"""
        return MoneyReceipt.objects.filter(company=self.request.user.company) \
                                  .select_related('customer', 'sale', 'company', 'seller', 'account')

    def apply_filters(self, queryset, request):
        """Apply filters to the queryset"""
        params = request.GET


        
        # Date range filtering
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(payment_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        # Customer filtering
        customer_id = params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Payment type filtering
        payment_type = params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        # Payment status filtering
        payment_status = params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        # Search filtering
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(mr_no__icontains=search) |
                Q(remark__icontains=search) |
                Q(payment_method__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(sale__invoice_no__icontains=search)
            )

        # Order by
        order_by = params.get('order_by', '-mr_no')
        if order_by.lstrip('-') in ['payment_date', 'amount', 'created_at', 'mr_no']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-payment_date')

        return queryset

    def get(self, request):
        """Get money receipts with filtering"""
        try:
            queryset = self.get_queryset()
            queryset = self.apply_filters(queryset, request)
            
            # Handle pagination
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request, view=self)
            
            if page is not None:
                serializer = MoneyReceiptSerializer(page, many=True, context={'request': request})
                return paginator.get_paginated_response(serializer.data, message="Money receipts fetched successfully.")
            
            # Non-paginated response
            serializer = MoneyReceiptSerializer(queryset, many=True, context={'request': request})
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} money receipts",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching money receipts: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="An error occurred while fetching money receipts.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # money_receipts/views.py - FIX THE POST METHOD

    def post(self, request):
        """Create new money receipt - FIXED VERSION"""
        try:
            logger.info("Creating money receipt", extra={
                'user': request.user.id,
                'company': getattr(request.user, 'company_id', None),
                'data': request.data
            })
            
            # Validate user has company
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User must be associated with a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Prepare data
            data = request.data.copy()
            
            # SUCCESS: FIXED: Remove company from data - let serializer handle it
            if 'company' in data:
                del data['company']
            
            # Validate required fields
            required_fields = ['customer_id', 'payment_date', 'payment_method', 'amount']
            missing_fields = [field for field in required_fields if field not in data or not data[field]]
            
            if missing_fields:
                return custom_response(
                    success=False,
                    message=f"Missing required fields: {', '.join(missing_fields)}",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # SUCCESS: FIXED: Pass request context to serializer
            serializer = MoneyReceiptSerializer(data=data, context={'request': request})
            
            if serializer.is_valid():
                receipt = serializer.save()
                logger.info(f"Money receipt created successfully: {receipt.mr_no}")
                
                return custom_response(
                    success=True,
                    message="Money receipt created successfully.",
                    data=MoneyReceiptSerializer(receipt, context={'request': request}).data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                logger.warning(f"Money receipt validation errors: {serializer.errors}")
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error creating money receipt: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="An error occurred while creating money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class MoneyReceiptDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, receipt_id, company):
        """Get money receipt object with company check"""
        try:
            return MoneyReceipt.objects.get(id=receipt_id, company=company)
        except MoneyReceipt.DoesNotExist:
            return None

    def get(self, request, receipt_id):
        """Get money receipt details"""
        try:
            receipt = self.get_object(receipt_id, request.user.company)
            if not receipt:
                return custom_response(
                    success=False,
                    message="Money receipt not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            serializer = MoneyReceiptSerializer(receipt, context={'request': request})
            return custom_response(
                success=True,
                message="Money receipt fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error fetching money receipt {receipt_id}: {str(e)}")
            return custom_response(
                success=False,
                message="An error occurred while fetching money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, receipt_id):
        """Update money receipt"""
        try:
            receipt = self.get_object(receipt_id, request.user.company)
            if not receipt:
                return custom_response(
                    success=False,
                    message="Money receipt not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            data = request.data.copy()
            serializer = MoneyReceiptSerializer(
                receipt, 
                data=data, 
                context={'request': request},
                partial=True
            )
            
            if serializer.is_valid():
                updated_receipt = serializer.save()
                logger.info(f"Money receipt updated: {updated_receipt.mr_no}")
                
                return custom_response(
                    success=True,
                    message="Money receipt updated successfully.",
                    data=MoneyReceiptSerializer(updated_receipt, context={'request': request}).data,
                    status_code=status.HTTP_200_OK
                )
            else:
                logger.warning(f"Money receipt update validation errors: {serializer.errors}")
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error updating money receipt {receipt_id}: {str(e)}")
            return custom_response(
                success=False,
                message="An error occurred while updating money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, receipt_id):
        """Delete money receipt"""
        try:
            receipt = self.get_object(receipt_id, request.user.company)
            if not receipt:
                return custom_response(
                    success=False,
                    message="Money receipt not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            mr_no = receipt.mr_no
            receipt.delete()
            logger.info(f"Money receipt deleted: {mr_no}")
            
            return custom_response(
                success=True,
                message="Money receipt deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error deleting money receipt {receipt_id}: {str(e)}")
            return custom_response(
                success=False,
                message="An error occurred while deleting money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )