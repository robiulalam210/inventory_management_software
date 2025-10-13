from rest_framework import viewsets, permissions
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer
from purchases.models import PurchaseItem

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class PurchaseViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return Purchase.objects.filter(company=user.company)
        return Purchase.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all().select_related('purchase', 'product')
    serializer_class = PurchaseItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]



