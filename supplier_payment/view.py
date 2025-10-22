from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Sum
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .serializers import SupplierPaymentSerializer
from .model import SupplierPayment
from purchases.models import Purchase
import logging

logger = logging.getLogger(__name__)

class SupplierPaymentListCreateAPIView(APIView):
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
        return SupplierPayment.objects.filter(company=self.request.user.company) \
                                    .select_related('supplier', 'purchase', 'company')

    def apply_filters(self, queryset, request):
        """Apply filters to the queryset"""
        # Date range filtering
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(payment_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        # Supplier filtering
        supplier_id = request.GET.get('supplier_id')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        # Purchase filtering
        purchase_id = request.GET.get('purchase_id')
        if purchase_id:
            queryset = queryset.filter(purchase_id=purchase_id)

        # Payment method filtering
        payment_method = request.GET.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        # Amount range filtering
        min_amount = request.GET.get('min_amount')
        max_amount = request.GET.get('max_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)

        # Status filtering
        status_filter = request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Search by reference, note, or cheque number
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference_no__icontains=search) |
                Q(note__icontains=search) |
                Q(cheque_no__icontains=search) |
                Q(supplier__name__icontains=search)
            )

        # Order by payment date (newest first by default)
        order_by = request.GET.get('order_by', '-payment_date')
        if order_by.lstrip('-') in ['payment_date', 'amount', 'created_at', 'reference_no']:
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
                SupplierPaymentSerializer,
                message="Supplier payments fetched successfully."
            )
            
        except Exception as e:
            logger.error(f"Error fetching supplier payments: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            logger.info("Creating supplier payment", extra={
                'user': request.user.id,
                'company': request.user.company.id,
                'data_received': request.data
            })
            
            # Prepare data
            data = request.data.copy()
            
            # Validate required fields
            required_fields = ['supplier_id', 'payment_date', 'payment_method', 'amount']
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
            
            # Handle purchase_id if provided
            purchase = None
            if 'purchase_id' in data and data['purchase_id']:
                try:
                    if isinstance(data['purchase_id'], str):
                        data['purchase_id'] = int(data['purchase_id'])
                    
                    try:
                        purchase = Purchase.objects.get(
                            id=data['purchase_id'], 
                            company=request.user.company
                        )
                        
                        # Check if payment amount exceeds due amount for specific purchase
                        if data['amount'] > purchase.due_amount:
                            logger.warning(f"Payment amount exceeds due amount: {data['amount']} > {purchase.due_amount}")
                            return custom_response(
                                success=False,
                                message=f"Payment amount ({data['amount']}) cannot be greater than due amount ({purchase.due_amount}) for purchase {purchase.invoice_no}",
                                data=None,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                            
                    except Purchase.DoesNotExist:
                        logger.warning(f"Purchase not found: {data['purchase_id']}")
                        return custom_response(
                            success=False,
                            message="Purchase not found",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                        
                except (ValueError, TypeError):
                    logger.warning(f"Invalid purchase_id format: {data['purchase_id']}")
                    return custom_response(
                        success=False,
                        message="Invalid purchase_id format",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # For overall payments, validate total due amount
            if not purchase and 'supplier_id' in data:
                try:
                    total_due = Purchase.objects.filter(
                        supplier_id=data['supplier_id'],
                        company=request.user.company,
                        due_amount__gt=0
                    ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0
                    
                    if data['amount'] > total_due:
                        logger.warning(f"Payment amount exceeds total due: {data['amount']} > {total_due}")
                        return custom_response(
                            success=False,
                            message=f"Payment amount ({data['amount']}) cannot be greater than total due amount ({total_due})",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                except Exception as e:
                    logger.error(f"Error calculating total due: {e}")
                    # Continue without validation if there's an error calculating total due
            
            # Handle cheque fields
            if data.get('payment_method') == 'cheque':
                cheque_required_fields = ['cheque_no', 'cheque_date']
                missing_cheque_fields = [field for field in cheque_required_fields if field not in data or data[field] in [None, '']]
                
                if missing_cheque_fields:
                    logger.warning(f"Missing cheque fields: {missing_cheque_fields}")
                    return custom_response(
                        success=False,
                        message=f"Missing required field for cheque payment: {', '.join(missing_cheque_fields)}",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = SupplierPaymentSerializer(
                data=data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                logger.info(f"Supplier payment created successfully: {instance.id}")
                
                return custom_response(
                    success=True,
                    message="Supplier payment created successfully.",
                    data=SupplierPaymentSerializer(instance, context={'request': request}).data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                logger.warning(f"Supplier payment validation errors: {serializer.errors}")
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error creating supplier payment: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SupplierPaymentDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, company):
        """Get supplier payment object with company check"""
        try:
            return SupplierPayment.objects.get(pk=pk, company=company)
        except SupplierPayment.DoesNotExist:
            return None

    def get(self, request, pk):
        try:
            payment = self.get_object(pk, request.user.company)
            if not payment:
                logger.warning(f"Supplier payment not found: {pk}")
                return custom_response(
                    success=False,
                    message="Supplier payment not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            serializer = SupplierPaymentSerializer(payment, context={'request': request})
            return custom_response(
                success=True,
                message="Supplier payment fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching supplier payment {pk}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        try:
            payment = self.get_object(pk, request.user.company)
            if not payment:
                logger.warning(f"Supplier payment not found for update: {pk}")
                return custom_response(
                    success=False,
                    message="Supplier payment not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            data = request.data.copy()
            
            # Convert amount to decimal if it's string
            if 'amount' in data and isinstance(data['amount'], str):
                try:
                    data['amount'] = float(data['amount'])
                except ValueError:
                    logger.warning(f"Invalid amount format in update: {data['amount']}")
                    return custom_response(
                        success=False,
                        message="Invalid amount format",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = SupplierPaymentSerializer(
                payment, 
                data=data, 
                context={'request': request},
                partial=True
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                logger.info(f"Supplier payment updated successfully: {instance.id}")
                
                return custom_response(
                    success=True,
                    message="Supplier payment updated successfully.",
                    data=SupplierPaymentSerializer(instance, context={'request': request}).data,
                    status_code=status.HTTP_200_OK
                )
            else:
                logger.warning(f"Supplier payment update validation errors: {serializer.errors}")
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error updating supplier payment {pk}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            payment = self.get_object(pk, request.user.company)
            if not payment:
                logger.warning(f"Supplier payment not found for deletion: {pk}")
                return custom_response(
                    success=False,
                    message="Supplier payment not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            payment_id = payment.id
            payment.delete()
            logger.info(f"Supplier payment deleted successfully: {payment_id}")
            
            return custom_response(
                success=True,
                message="Supplier payment deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error deleting supplier payment {pk}: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )