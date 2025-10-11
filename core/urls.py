# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Purchases
from purchases.views import SupplierViewSet, PurchaseViewSet, PurchaseItemViewSet

# Sales
from sales.views import SaleViewSet, SaleItemViewSet, CustomerViewSet, DuePaymentAPIView

# Products
from products.views import ProductViewSet, CategoryViewSet, UnitViewSet, BrandViewSet, GroupViewSet, SourceViewSet

router = DefaultRouter()

# Product routes
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'units', UnitViewSet, basename='unit')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'sources', SourceViewSet, basename='source')

# Sales routes
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'sale-items', SaleItemViewSet, basename='sale-item')
router.register(r'customers', CustomerViewSet, basename='customer')

# Purchases routes
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchases', PurchaseViewSet, basename='purchase')
router.register(r'purchase-items', PurchaseItemViewSet, basename='purchase-item')

urlpatterns = [
    path('', include(router.urls)),
    path('pay-due/', DuePaymentAPIView.as_view(), name='pay_due'),
]
