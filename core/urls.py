from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, ProfileView, MyTokenObtainPairView,
    CategoryViewSet, UnitViewSet, ProductViewSet,
    SupplierViewSet, PurchaseListCreateView, PurchaseRetrieveView,
    CustomerListCreateView, CustomerRetrieveUpdateDestroyView,
    SaleListCreateView, SaleRetrieveView,   SalesReportView, PurchaseReportView, ProfitLossReportView, LowStockReportView   
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('units', UnitViewSet)
router.register('products', ProductViewSet)
router.register('suppliers', SupplierViewSet)

urlpatterns = [
    # 🔐 Auth APIs
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),

    # 🧾 Main APIs
    path('', include(router.urls)),

    # 📦 Purchase
    path('purchases/', PurchaseListCreateView.as_view(), name='purchase-list'),
    path('purchases/<int:pk>/', PurchaseRetrieveView.as_view(), name='purchase-detail'),

    # 👥 Customer
    path('customers/', CustomerListCreateView.as_view(), name='customer-list-create'),
    path('customers/<int:pk>/', CustomerRetrieveUpdateDestroyView.as_view(), name='customer-detail'),

    # 💰 Sales
    path('sales/', SaleListCreateView.as_view(), name='sale-list-create'),
    path('sales/<int:pk>/', SaleRetrieveView.as_view(), name='sale-detail'),

      path('reports/sales/', SalesReportView.as_view(), name='sales-report'),
    path('reports/purchases/', PurchaseReportView.as_view(), name='purchase-report'),
        path('reports/profit-loss/', ProfitLossReportView.as_view(), name='profit-loss-report'),
    path('reports/low-stock/', LowStockReportView.as_view(), name='low-stock-report'),
]
