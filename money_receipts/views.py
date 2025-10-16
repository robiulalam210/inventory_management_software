from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import MoneyReceiptSerializer
from .models import MoneyReceipt
from core.utils import custom_response

class MoneyReceiptCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            receipts = MoneyReceipt.objects.filter(company=request.user.company)
            serializer = MoneyReceiptSerializer(receipts, many=True)
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
                if field not in data:
                    return custom_response(
                        success=False,
                        message=f"Missing required field: {field}",
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
                    data=MoneyReceiptSerializer(instance).data,
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