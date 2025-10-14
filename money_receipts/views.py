from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import MoneyReceiptSerializer
from .models import MoneyReceipt
from core.utils import custom_response
class MoneyReceiptCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        receipts = MoneyReceipt.objects.filter(company=request.user.company)
        serializer = MoneyReceiptSerializer(receipts, many=True)
        return custom_response(
            success=True,
            message="Money receipts fetched.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = MoneyReceiptSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            instance = serializer.save(
                company=request.user.company,
                seller=request.user
            )
            return custom_response(
                success=True,
                message="Money receipt created.",
                data=MoneyReceiptSerializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        return custom_response(
            success=False,
            message="Validation Error.",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )