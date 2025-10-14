from rest_framework import viewsets, permissions
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company."""
    company_field = 'company'  # override in subclass if needed

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()

# Suppliers
class SupplierViewSet(BaseCompanyViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Purchases
class PurchaseViewSet(BaseCompanyViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

# Purchase Items
class PurchaseItemViewSet(BaseCompanyViewSet):
    queryset = PurchaseItem.objects.all().select_related('purchase', 'product')
    serializer_class = PurchaseItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    company_field = 'purchase__company'  # filter through related Purchase
