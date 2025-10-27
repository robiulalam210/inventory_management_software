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

    def get_paginated_response(self, queryset, request, serializer_class, message="Data fetched successfully."):
        """Helper method to handle pagination"""
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        
        if page is not None:
            serializer = serializer_class(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data, message=message)
        
        # If no pagination, return all results
        serializer = serializer_class(queryset, many=True, context={'request': request})
        return custom_response(
            success=True,
            message=message,
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def get_queryset(self):
        """Base queryset with company filtering"""
        return MoneyReceipt.objects.filter(company=self.request.user.company) \
                                  .select_related('customer', 'sale', 'company', 'seller')

    def apply_filters(self, queryset, request):
        """Apply filters to the queryset - SIMPLIFIED VERSION"""
        # Date range filtering
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(payment_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        # Customer filtering - by ID only
        customer = request.GET.get('customer')
        if customer:
            queryset = queryset.filter(customer_id=customer)

        # Seller filtering - by ID only
        seller = request.GET.get('seller')
        if seller:
            queryset = queryset.filter(seller_id=seller)

        # Payment method filtering
        payment_method = request.GET.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method__icontains=payment_method)

        # Search filtering - ONLY direct fields on MoneyReceipt model
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(mr_no__icontains=search) |
                Q(remark__icontains=search) |
                Q(payment_method__icontains=search) |
                Q(amount__icontains=search)
            )

        # Order by payment date (newest first by default)
        order_by = request.GET.get('order_by', '-payment_date')
        if order_by.lstrip('-') in ['payment_date', 'amount', 'created_at', 'mr_no']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-payment_date')

        return queryset

    def get(self, request):
        try:
            # Get base queryset
            queryset = self.get_queryset()
            
            # Apply filters
            queryset = self.apply_filters(queryset, request)
            
            # Return paginated response
            return self.get_paginated_response(
                queryset, 
                request, 
                MoneyReceiptSerializer,
                message="Money receipts fetched successfully."
            )
            
        except Exception as e:
            logger.error(f"Error fetching money receipts: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="An error occurred while fetching money receipts.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            logger.info("Creating money receipt", extra={
                'user': request.user.id,
                'company': request.user.company.id,
                'data_received': request.data
            })
            
            # Prepare data
            data = request.data.copy()
            data['company'] = request.user.company.id
            
            # Make all fields optional except basic ones
            required_fields = ['customer', 'payment_date', 'payment_method', 'amount']
            missing_fields = [field for field in required_fields if field not in data or data[field] in [None, '']]
            
            if missing_fields:
                logger.warning(f"Missing required fields: {missing_fields}")
                return custom_response(
                    success=False,
                    message=f"Missing required fields: {', '.join(missing_fields)}",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert amount to decimal if it's string
            if 'amount' in data and isinstance(data['amount'], str):
                try:
                    data['amount'] = float(data['amount'])
                except ValueError:
                    logger.warning(f"Invalid amount format: {data['amount']}")
                    return custom_response(
                        success=False,
                        message="Invalid amount format",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = MoneyReceiptSerializer(
                data=data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                logger.info(f"Money receipt created successfully: {instance.id}")
                
                return custom_response(
                    success=True,
                    message="Money receipt created successfully.",
                    data=MoneyReceiptSerializer(instance, context={'request': request}).data,
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
            logger.error(f"Error fetching money receipt {receipt_id}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="An error occurred while fetching money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, receipt_id):
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
            data['company'] = request.user.company.id
            
            serializer = MoneyReceiptSerializer(
                receipt, 
                data=data, 
                context={'request': request},
                partial=True
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                logger.info(f"Money receipt updated successfully: {instance.id}")
                
                return custom_response(
                    success=True,
                    message="Money receipt updated successfully.",
                    data=MoneyReceiptSerializer(instance, context={'request': request}).data,
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
            logger.error(f"Error updating money receipt {receipt_id}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="An error occurred while updating money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, receipt_id):
        try:
            receipt = self.get_object(receipt_id, request.user.company)
            if not receipt:
                return custom_response(
                    success=False,
                    message="Money receipt not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            receipt_id_val = receipt.id
            receipt.delete()
            logger.info(f"Money receipt deleted successfully: {receipt_id_val}")
            
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
                message="An error occurred while deleting money receipt.",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )