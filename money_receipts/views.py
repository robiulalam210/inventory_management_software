from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import MoneyReceiptSerializer
from .models import MoneyReceipt
from core.utils import custom_response
import json

class MoneyReceiptCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            receipts = MoneyReceipt.objects.filter(company=request.user.company)
            serializer = MoneyReceiptSerializer(receipts, many=True, context={'request': request})
            return custom_response(
                success=True,
                message="Money receipts fetched successfully.",
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
            print("Received money receipt data:", request.data)
            
            # Prepare data
            data = request.data.copy()
            
            # Validate required fields
            required_fields = ['customer_id', 'payment_date', 'payment_method', 'amount']
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
            
            # Handle sale_id if provided
            if 'sale_id' in data and data['sale_id']:
                try:
                    # Convert to integer if it's string
                    if isinstance(data['sale_id'], str):
                        data['sale_id'] = int(data['sale_id'])
                except (ValueError, TypeError):
                    return custom_response(
                        success=False,
                        message="Invalid sale_id format",
                        data=None,
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = MoneyReceiptSerializer(
                data=data, 
                context={'request': request}
            )
            
            if serializer.is_valid():
                instance = serializer.save()
                return custom_response(
                    success=True,
                    message="Money receipt created successfully.",
                    data=MoneyReceiptSerializer(instance, context={'request': request}).data,
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
            print("Error in money receipt creation:", str(e))
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )