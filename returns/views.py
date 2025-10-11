# core/views.py
from rest_framework import viewsets
from .models import SalesReturn, PurchaseReturn, BadStock
from .serializers import SalesReturnSerializer, PurchaseReturnSerializer, BadStockSerializer

class SalesReturnViewSet(viewsets.ModelViewSet):
    queryset = SalesReturn.objects.all()
    serializer_class = SalesReturnSerializer

class PurchaseReturnViewSet(viewsets.ModelViewSet):
    queryset = PurchaseReturn.objects.all()
    serializer_class = PurchaseReturnSerializer

class BadStockViewSet(viewsets.ModelViewSet):
    queryset = BadStock.objects.all()
    serializer_class = BadStockSerializer
