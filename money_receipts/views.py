from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .serializers import MoneyReceiptSerializer
from .models import MoneyReceipt
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class MoneyReceiptCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Base queryset with company filtering"""
        user = self.request.user
        if not hasattr(user, 'company') or not user.company:
            logger.warning(f"User {user.username} has no company association")
            return MoneyReceipt.objects.none()
        
        queryset = MoneyReceipt.objects.filter(company=user.company)
        
        # SAFE select_related - only include essential relationships
        try:
            queryset = queryset.select_related(
                'customer', 'company', 'seller'
            )
            # Use prefetch_related for optional relationships
            queryset = queryset.prefetch_related('sale', 'account')
        except Exception as e:
            logger.warning(f"Error in select_related: {e}. Using minimal queryset.")
        
        return queryset

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
                Q(payment_method__icontains=search)
            )
            # Safe related field search
            try:
                if search:
                    queryset = queryset.filter(
                        Q(customer__name__icontains=search) |
                        Q(sale__invoice_no__icontains=search)
                    )
            except Exception as e:
                logger.warning(f"Error in related field search: {e}")

        # Order by
        order_by = params.get('order_by', '-payment_date')
        valid_order_fields = ['payment_date', 'amount', 'created_at', 'mr_no', 'id']
        
        # Remove - prefix to check field
        order_field = order_by.lstrip('-')
        if order_field in valid_order_fields:
            try:
                queryset = queryset.order_by(order_by)
            except Exception as e:
                logger.warning(f"Error ordering by {order_by}: {e}")
                queryset = queryset.order_by('-payment_date')
        else:
            queryset = queryset.order_by('-payment_date')

        return queryset

    def get(self, request):
        """Get money receipts with filtering - FIXED VERSION"""
        try:
            # Check user company
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User must be associated with a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Fetching money receipts for company: {request.user.company.name}")
            
            # Get base queryset
            queryset = self.get_queryset()
            logger.info(f"Initial queryset count: {queryset.count()}")
            
            # Apply filters
            filtered_queryset = self.apply_filters(queryset, request)
            logger.info(f"After filtering count: {filtered_queryset.count()}")
            
            # Handle pagination
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(filtered_queryset, request, view=self)
            
            if page is not None:
                try:
                    serializer = MoneyReceiptSerializer(page, many=True, context={'request': request})
                    return paginator.get_paginated_response(serializer.data, message="Money receipts fetched successfully.")
                except Exception as serializer_error:
                    logger.error(f"Serializer error: {serializer_error}", exc_info=True)
                    
                    # Fallback to simple data
                    simple_data = []
                    for receipt in page:
                        simple_data.append({
                            'id': receipt.id,
                            'mr_no': receipt.mr_no,
                            'amount': float(receipt.amount),
                            'payment_date': receipt.payment_date,
                            'customer_name': receipt.customer.name if receipt.customer else None,
                            'payment_method': receipt.payment_method,
                            'payment_status': receipt.payment_status
                        })
                    
                    return paginator.get_paginated_response(simple_data, message="Money receipts fetched (simplified).")
            
            # Non-paginated response
            try:
                serializer = MoneyReceiptSerializer(filtered_queryset, many=True, context={'request': request})
                return custom_response(
                    success=True,
                    message=f"Found {filtered_queryset.count()} money receipts",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            except Exception as serializer_error:
                logger.error(f"Non-paginated serializer error: {serializer_error}")
                # Return minimal data
                minimal_data = list(filtered_queryset.values(
                    'id', 'mr_no', 'amount', 'payment_date', 'payment_method', 'payment_status'
                ))
                return custom_response(
                    success=True,
                    message=f"Found {filtered_queryset.count()} money receipts (minimal data)",
                    data=minimal_data,
                    status_code=status.HTTP_200_OK
                )
            
        except Exception as e:
            logger.error(f"Error fetching money receipts: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=f"An error occurred while fetching money receipts: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create new money receipt - FIXED VERSION"""
        try:
            logger.info("Creating money receipt", extra={
                'user': request.user.username,
                'company': getattr(request.user, 'company_id', None),
                'data_keys': list(request.data.keys())
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
            logger.info(f"Received data: {data}")
            
            # Add company to data for serializer validation
            data['company'] = request.user.company.id
            
            # Validate required fields
            required_fields = ['amount', 'payment_date', 'payment_method']
            missing_fields = [field for field in required_fields if field not in data or data[field] in [None, '']]
            
            if missing_fields:
                return custom_response(
                    success=False,
                    message=f"Missing required fields: {', '.join(missing_fields)}",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate amount
            try:
                amount = Decimal(str(data['amount']))
                if amount <= 0:
                    return custom_response(
                        success=False,
                        message="Amount must be greater than 0.",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return custom_response(
                    success=False,
                    message="Invalid amount format.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Create serializer with context
            serializer = MoneyReceiptSerializer(data=data, context={'request': request})
            
            if serializer.is_valid():
                try:
                    receipt = serializer.save()
                    logger.info(f"Money receipt created successfully: {receipt.mr_no}")
                    
                    # Return full receipt data
                    response_serializer = MoneyReceiptSerializer(receipt, context={'request': request})
                    return custom_response(
                        success=True,
                        message="Money receipt created successfully.",
                        data=response_serializer.data,
                        status_code=status.HTTP_201_CREATED
                    )
                except Exception as save_error:
                    logger.error(f"Error saving money receipt: {save_error}", exc_info=True)
                    return custom_response(
                        success=False,
                        message=f"Error saving money receipt: {str(save_error)}",
                        data=None,
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
                message=f"An error occurred while creating money receipt: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MoneyReceiptDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, receipt_id, company):
        """Get money receipt object with company check - FIXED"""
        try:
            return MoneyReceipt.objects.filter(
                id=receipt_id, 
                company=company
            ).select_related('customer', 'company').first()
        except Exception as e:
            logger.error(f"Error getting money receipt {receipt_id}: {e}")
            return None

    def get(self, request, receipt_id):
        """Get money receipt details - FIXED"""
        try:
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User must be associated with a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
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
            logger.error(f"Error fetching money receipt {receipt_id}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=f"An error occurred while fetching money receipt: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, receipt_id):
        """Update money receipt - FIXED"""
        try:
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User must be associated with a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            receipt = self.get_object(receipt_id, request.user.company)
            if not receipt:
                return custom_response(
                    success=False,
                    message="Money receipt not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            data = request.data.copy()
            
            # Remove immutable fields
            immutable_fields = ['mr_no', 'company', 'created_at', 'updated_at']
            for field in immutable_fields:
                if field in data:
                    del data[field]
            
            serializer = MoneyReceiptSerializer(
                receipt, 
                data=data, 
                context={'request': request},
                partial=True
            )
            
            if serializer.is_valid():
                try:
                    updated_receipt = serializer.save()
                    logger.info(f"Money receipt updated: {updated_receipt.mr_no}")
                    
                    return custom_response(
                        success=True,
                        message="Money receipt updated successfully.",
                        data=MoneyReceiptSerializer(updated_receipt, context={'request': request}).data,
                        status_code=status.HTTP_200_OK
                    )
                except Exception as save_error:
                    logger.error(f"Error saving updated money receipt: {save_error}")
                    return custom_response(
                        success=False,
                        message=f"Error saving updates: {str(save_error)}",
                        data=None,
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            logger.error(f"Error updating money receipt {receipt_id}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=f"An error occurred while updating money receipt: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, receipt_id):
        """Delete money receipt - FIXED"""
        try:
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User must be associated with a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
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
            logger.error(f"Error deleting money receipt {receipt_id}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=f"An error occurred while deleting money receipt: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )