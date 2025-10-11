from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Sale, SaleItem, Customer
from .serializers import SaleSerializer, SaleItemSerializer, CustomerSerializer, DuePaymentSerializer

# -----------------------------
# Sale ViewSet
# -----------------------------
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

# -----------------------------
# SaleItem ViewSet
# -----------------------------
class SaleItemViewSet(viewsets.ModelViewSet):
    queryset = SaleItem.objects.all()
    serializer_class = SaleItemSerializer

# -----------------------------
# Customer ViewSet
# -----------------------------
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

# -----------------------------
# Due Payment API
# -----------------------------
class DuePaymentAPIView(APIView):
    def post(self, request, *args, **kwargs):
        print("Request Data:", request.data)
        serializer = DuePaymentSerializer(data=request.data)
        if serializer.is_valid():
            sale = serializer.save()
            print("Payment Success:", sale.paid_amount, sale.due_amount)
            return Response({
                "message": "Payment successful.",
                "sale_id": sale.id,
                "paid_amount": str(sale.paid_amount),
                "due_amount": str(sale.due_amount)
            })
        print("Errors:", serializer.errors)
        return Response(serializer.errors, status=400)
