from rest_framework import viewsets, permissions
from .models import SalesReturn, PurchaseReturn, BadStock
from .serializers import SalesReturnSerializer, PurchaseReturnSerializer, BadStockSerializer
# reports/views.py
from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from returns.models import SalesReturn, SalesReturnItem, PurchaseReturn, PurchaseReturnItem, BadStock




class SalesReturnViewSet(viewsets.ModelViewSet):
    serializer_class = SalesReturnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return SalesReturn.objects.filter(company=user.company)
        return SalesReturn.objects.none()

    def perform_create(self, serializer):
        company = getattr(self.request.user, 'company', None)
        serializer.save(company=company)
    
class PurchaseReturnViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseReturnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return PurchaseReturn.objects.filter(company=user.company)
        return PurchaseReturn.objects.none()

    def perform_create(self, serializer):
        company = getattr(self.request.user, 'company', None)
        serializer.save(company=company)

class BadStockViewSet(viewsets.ModelViewSet):
    serializer_class = BadStockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return BadStock.objects.filter(company=user.company)
        return BadStock.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, 'company', None)
        serializer.save(company=company)