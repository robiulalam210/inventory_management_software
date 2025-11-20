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
from rest_framework import serializers

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
        # ... your existing filter logic ...
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

        # supplier_payment/views.py - FIXED VERSION
    def post(self, request):
        """Create a new supplier payment"""
        try:
            # Log the incoming data for debugging
            logger.info(f"=== SUPPLIER PAYMENT CREATION DEBUG ===")
            logger.info(f"Raw request data: {request.data}")
            
            # Create a mutable copy of the data
            data = request.data.copy()
            
            # ✅ FIXED: Map seller_id to created_by (not prepared_by)
            field_mappings = {
                'account_id': 'account',
                'supplier_id': 'supplier', 
                'seller_id': 'created_by',  # ✅ FIXED: seller_id -> created_by
                'purchase_id': 'purchase',
            }
            
            for old_field, new_field in field_mappings.items():
                if old_field in data:
                    data[new_field] = data.pop(old_field)
                    logger.info(f"Mapped {old_field} -> {new_field}: {data[new_field]}")
            
            # Handle specific_invoice logic
            specific_invoice = data.get('specific_invoice', False)
            invoice_no = data.get('invoice_no')
            
            if specific_invoice and invoice_no:
                try:
                    # Find the purchase by invoice_no
                    purchase = Purchase.objects.get(
                        invoice_no=invoice_no,
                        company=request.user.company
                    )
                    data['purchase'] = purchase.id
                    logger.info(f"Found purchase for invoice {invoice_no}: {purchase.id}")
                except Purchase.DoesNotExist:
                    logger.warning(f"Purchase not found for invoice: {invoice_no}")
                    return custom_response(
                        success=False,
                        message=f"Purchase with invoice number {invoice_no} not found",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            logger.info(f"Final data before serializer: {data}")
            
            serializer = SupplierPaymentSerializer(data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            
            # ✅ FIXED: Use created_by (matching the model field)
            payment = serializer.save(
                company=request.user.company,
                created_by=request.user  # ✅ CORRECT: created_by matches model
            )
            
            logger.info(f"Supplier payment created successfully: {payment.sp_no}")
            logger.info("=== SUPPLIER PAYMENT CREATION COMPLETE ===")
            
            return custom_response(
                success=True,
                message="Supplier payment created successfully",
                data=SupplierPaymentSerializer(payment, context={'request': request}).data,
                status_code=status.HTTP_201_CREATED
            )
            
        except serializers.ValidationError as e:
            logger.warning(f"Supplier payment validation error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating supplier payment: {str(e)}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return custom_response(
                success=False,
                message="Internal server error",
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