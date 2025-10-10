from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().select_related('supplier').prefetch_related('items')
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['supplier', 'date']
    search_fields = ['supplier__name']


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all().select_related('purchase', 'product')
    serializer_class = PurchaseItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
