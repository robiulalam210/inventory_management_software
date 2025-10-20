# supplier_payment/views.py
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import SupplierPaymentSerializer
from .model import SupplierPayment
from purchases.models import Purchase  # ✅ ADDED: Import Purchase model
from core.utils import custom_response
import json

class SupplierPaymentListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            payments = SupplierPayment.objects.filter(company=request.user.company)
            serializer = SupplierPaymentSerializer(payments, many=True, context={'request': request})
            return custom_response(
                success=True,
                message="Supplier payments fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            print("Received supplier payment data:", request.data)
            
            # Prepare data
            data = request.data.copy()
            
            # Validate required fields
            required_fields = ['supplier_id', 'payment_date', 'payment_method', 'amount']
            for field in required_fields:
                if field not in data or data[field] in [None, '']:
                    return custom_response(
                        success=False,
                        message=f"Missing required field: {field}",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # Convert amount to decimal if it's string
            if 'amount' in data and isinstance(data['amount'], str):
                try:
                    data['amount'] = float(data['amount'])
                except ValueError:
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
                    # Convert to integer if it's string
                    if isinstance(data['purchase_id'], str):
                        data['purchase_id'] = int(data['purchase_id'])
                    
                    # ✅ FIXED: Purchase is now imported, so this will work
                    try:
                        purchase = Purchase.objects.get(
                            id=data['purchase_id'], 
                            company=request.user.company
                        )
                        
                        # Check if payment amount exceeds due amount for specific purchase
                        if purchase and data['amount'] > purchase.due_amount:
                            return custom_response(
                                success=False,
                                message=f"Payment amount ({data['amount']}) cannot be greater than due amount ({purchase.due_amount}) for purchase {purchase.invoice_no}",
                                data=None,
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                            
                    except Purchase.DoesNotExist:
                        return custom_response(
                            success=False,
                            message="Purchase not found",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                        
                except (ValueError, TypeError):
                    return custom_response(
                        success=False,
                        message="Invalid purchase_id format",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # For overall payments, validate total due amount
            if not purchase and 'supplier_id' in data:
                from django.db.models import Sum
                
                try:
                    total_due = Purchase.objects.filter(
                        supplier_id=data['supplier_id'],
                        company=request.user.company,
                        due_amount__gt=0
                    ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0
                    
                    if data['amount'] > total_due:
                        return custom_response(
                            success=False,
                            message=f"Payment amount ({data['amount']}) cannot be greater than total due amount ({total_due})",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                except Exception as e:
                    print(f"Error calculating total due: {e}")
                    # Continue without validation if there's an error calculating total due
            
            # Handle cheque fields
            if data.get('payment_method') == 'cheque':
                cheque_required_fields = ['cheque_no', 'cheque_date']
                for field in cheque_required_fields:
                    if field not in data or data[field] in [None, '']:
                        return custom_response(
                            success=False,
                            message=f"Missing required field for cheque payment: {field}",
                            data=None,
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
            
            serializer = SupplierPaymentSerializer(
                data=data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                return custom_response(
                    success=True,
                    message="Supplier payment created successfully.",
                    data=SupplierPaymentSerializer(instance, context={'request': request}).data,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                print("Validation errors:", serializer.errors)
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            print("Error in supplier payment creation:", str(e))
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SupplierPaymentDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, company):
        try:
            return SupplierPayment.objects.get(pk=pk, company=company)
        except SupplierPayment.DoesNotExist:
            return None

    def get(self, request, pk):
        try:
            payment = self.get_object(pk, request.user.company)
            if not payment:
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
                return custom_response(
                    success=True,
                    message="Supplier payment updated successfully.",
                    data=SupplierPaymentSerializer(instance, context={'request': request}).data,
                    status_code=status.HTTP_200_OK
                )
            else:
                return custom_response(
                    success=False,
                    message="Validation error occurred.",
                    data=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            print("Error in supplier payment update:", str(e))
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
                return custom_response(
                    success=False,
                    message="Supplier payment not found.",
                    data=None,
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            payment.delete()
            return custom_response(
                success=True,
                message="Supplier payment deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )