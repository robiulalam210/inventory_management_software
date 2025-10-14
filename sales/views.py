from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Sale, SaleItem, Customer
from .serializers import (
    SaleSerializer, 
    SaleItemSerializer, 
    CustomerSerializer, 
    DuePaymentSerializer
)

# -----------------------------
# BaseCompanyViewSet
# -----------------------------
class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'  # override if needed

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()


# -----------------------------
# Sale ViewSet
# -----------------------------
class SaleViewSet(BaseCompanyViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


# -----------------------------
# SaleItem ViewSet
# -----------------------------
class SaleItemViewSet(BaseCompanyViewSet):
    queryset = SaleItem.objects.all().select_related('sale', 'product')
    serializer_class = SaleItemSerializer
    permission_classes = [IsAuthenticated]
    company_field = 'sale__company'  # filter through related Sale


# -----------------------------
# Customer ViewSet
# -----------------------------
class CustomerViewSet(BaseCompanyViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # optionally order by name
        return super().get_queryset().order_by('name')

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, 'company', None)

        # If staff, get company from staff profile
        if not company and hasattr(user, 'staff') and user.staff:
            company = getattr(user.staff, 'company', None)

        # role-based handling
        role = getattr(user, 'role', None)
        if role == 'staff' and not company:
            raise serializers.ValidationError("Staff user must belong to a company.")

        serializer.save(company=company)


# -----------------------------
# Due Payment API
# -----------------------------
class DuePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = DuePaymentSerializer(data=request.data)
        serializer.context['request'] = request  # ensure request context is passed
        if serializer.is_valid(raise_exception=True):
            sale = serializer.save()
            return Response({
                "success": True,
                "message": "Payment successful.",
                "sale_id": sale.id,
                "paid_amount": str(sale.paid_amount),
                "due_amount": str(sale.payable_amount - sale.paid_amount),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)