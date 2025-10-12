# core/views.py
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from purchases.models import Supplier, Purchase, PurchaseItem
from purchases.serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        # Only return purchases of the logged-in user's company
        user = self.request.user
        return Purchase.objects.filter(company=user.company)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all().select_related('purchase', 'product')
    serializer_class = PurchaseItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
