from rest_framework import viewsets, status
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
# Sale ViewSet
# -----------------------------
class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter sales by the logged-in user's company."""
        user = self.request.user
        queryset = Sale.objects.all()
        if hasattr(user, 'company'):
            queryset = queryset.filter(company=user.company)
        return queryset.order_by('-id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})  # pass request for company check
        return context


# -----------------------------
# SaleItem ViewSet
# -----------------------------
class SaleItemViewSet(viewsets.ModelViewSet):
    serializer_class = SaleItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only allow sale items belonging to user's company sales."""
        user = self.request.user
        queryset = SaleItem.objects.all()
        if hasattr(user, 'company'):
            queryset = queryset.filter(sale__company=user.company)
        return queryset


# -----------------------------
# Customer ViewSet
# -----------------------------
class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Customer.objects.all()
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        return queryset.order_by('name')

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, 'company', None)

        # staff profile থেকে company বের করো
        if not company and hasattr(user, 'staff') and user.staff:
            company = getattr(user.staff, 'company', None)

        # role অনুযায়ী check
        role = getattr(user, 'role', None)
        if role == 'admin':
            company = company or None
        elif role == 'staff':
            if not company:
                raise serializers.ValidationError("Staff user must belong to a company.")
        elif role == 'customer':
            company = company or None

        serializer.save(company=company)




# -----------------------------
# Due Payment API
# -----------------------------
class DuePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = DuePaymentSerializer(data=request.data)
        if serializer.is_valid():
            sale = serializer.save()
            return Response({
                "message": "Payment successful.",
                "sale_id": sale.id,
                "paid_amount": str(sale.paid_amount),
                "due_amount": str(sale.payable_amount - sale.paid_amount),
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


