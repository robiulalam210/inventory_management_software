from rest_framework import generics, permissions, filters, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum


from .models import User, Supplier, Purchase, Customer, Sale, Category, Unit, Product
from .serializers import CategorySerializer, UnitSerializer, ProductSerializer
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    SupplierSerializer,
    PurchaseSerializer,
    CustomerSerializer,
    SaleSerializer
)

# ----------------- 🔐 Authentication -----------------
class MyTokenObtainPairView(TokenObtainPairView):
    """Custom JWT Login"""
    pass


class RegisterView(generics.CreateAPIView):
    """User registration"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveAPIView):
    """Get logged-in user profile"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

# ----------------- 🏷 Category -----------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
# ----------------- Unit -----------------
class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

# ----------------- Category -----------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

# ----------------- Product -----------------
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'unit']
    search_fields = ['name', 'category__name']
    ordering_fields = ['name', 'stock', 'price']             
# ----------------- 🏢 Supplier -----------------
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name']


# ----------------- 📦 Purchase -----------------
class PurchaseListCreateView(generics.ListCreateAPIView):
    queryset = Purchase.objects.all().order_by('-purchase_date')
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'product']
    search_fields = ['product__name', 'supplier__name']
    ordering_fields = ['purchase_date', 'total', 'quantity']

    def perform_create(self, serializer):
        """Auto increase stock after purchase"""
        purchase = serializer.save()
        product = purchase.product
        product.stock += purchase.quantity
        product.save()


class PurchaseRetrieveView(generics.RetrieveAPIView):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------- 👥 Customer -----------------
class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


class CustomerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------- 💰 Sale -----------------
class SaleListCreateView(generics.ListCreateAPIView):
    queryset = Sale.objects.all().order_by('-sale_date')
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer', 'product']
    search_fields = ['product__name', 'customer__name']
    ordering_fields = ['sale_date', 'total', 'quantity']

    def perform_create(self, serializer):
        """Auto decrease stock after sale"""
        sale = serializer.save()
        product = sale.product
        if product.stock >= sale.quantity:
            product.stock -= sale.quantity
            product.save()
        else:
            raise ValueError("Insufficient stock!")


class SaleRetrieveView(generics.RetrieveAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    # permission_classes = [permissions.IsAuthenticated]

# ----------------- Customer -----------------
class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all().order_by('-id')
    serializer_class = CustomerSerializer
    # permission_classes = [permissions.IsAuthenticated]


class CustomerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    # permission_classes = [permissions.IsAuthenticated]


# ----------------- Sale -----------------
class SaleListCreateView(generics.ListCreateAPIView):
    queryset = Sale.objects.all().order_by('-sale_date')
    serializer_class = SaleSerializer
    # permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer', 'product']
    search_fields = ['customer__name', 'product__name']
    ordering_fields = ['sale_date', 'total', 'quantity']


class SaleRetrieveView(generics.RetrieveAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]


class SalesReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        location = request.GET.get('location')  # 🔹 Filter by location

        sales = Sale.objects.filter(sale_date__range=[start_date, end_date])
        if location:
            sales = sales.filter(location=location)

        total_sales = sales.aggregate(total=Sum('total'), quantity=Sum('quantity'))
        serializer = SaleSerializer(sales, many=True)
        
        return Response({
            "sales": serializer.data,
            "summary": total_sales
        })
class PurchaseReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        location = request.GET.get('location')  # 🔹 Filter by location

        purchases = Purchase.objects.filter(purchase_date__range=[start_date, end_date])
        if location:
            purchases = purchases.filter(location=location)

        total_purchase = purchases.aggregate(total=Sum('total'), quantity=Sum('quantity'))
        serializer = PurchaseSerializer(purchases, many=True)

        return Response({
            "purchases": serializer.data,
            "summary": total_purchase
        })
    

class ProfitLossReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        location = request.GET.get('location')  # optional

        sales = Sale.objects.filter(sale_date__range=[start_date, end_date])
        purchases = Purchase.objects.filter(purchase_date__range=[start_date, end_date])
        
        if location:
            sales = sales.filter(location=location)
            purchases = purchases.filter(location=location)

        total_sales = sales.aggregate(total_sales=Sum('total'))['total_sales'] or 0
        total_purchase = purchases.aggregate(total_purchase=Sum('total'))['total_purchase'] or 0
        profit_loss = total_sales - total_purchase

        return Response({
            "total_sales": total_sales,
            "total_purchase": total_purchase,
            "profit_loss": profit_loss
        })
    
class LowStockReportView(APIView):
    def get(self, request):
        threshold = request.GET.get('threshold', 10)  # default 10 units
        threshold = int(threshold)

        low_stock_products = Product.objects.filter(stock__lte=threshold).order_by('stock')
        
        data = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category.name,
                "unit": p.unit.name,
                "stock": p.stock,
                "price": p.price,
            } for p in low_stock_products
        ]

        return Response({
            "threshold": threshold,
            "low_stock_products": data,
            "count": len(data)
        })