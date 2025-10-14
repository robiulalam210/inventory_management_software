from django.urls import path, include
from rest_framework.routers import DefaultRouter

from money_receipts.views import MoneyReceiptCreateAPIView  
from .views import CustomLoginView
from rest_framework_simplejwt.views import TokenRefreshView

# Purchases
from purchases.views import  PurchaseViewSet, PurchaseItemViewSet
from suppliers.views import SupplierViewSet  # ঠিক path

# Sales
from sales.views import SaleViewSet, SaleItemViewSet, DuePaymentAPIView
from customers.views import CustomerViewSet  # ঠিক path

# Products
from products.views import ProductViewSet, CategoryViewSet, UnitViewSet, BrandViewSet, GroupViewSet, SourceViewSet
from .views import CompanyViewSet, UserViewSet, StaffRoleViewSet, StaffViewSet

# Returns (make sure these exist in core/views.py or create returns/views.py)
from returns.views import SalesReturnViewSet, PurchaseReturnViewSet, BadStockViewSet
from accounts.views import AccountViewSet  # ঠিক path

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'users', UserViewSet)
router.register(r'staff-roles', StaffRoleViewSet)
router.register(r'staffs', StaffViewSet)
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
# router.register(r'money-receipts', MoneyReceiptCreateAPIView, basename='money-receipt')

# Purchases routes
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchases', PurchaseViewSet, basename='purchase')
router.register(r'purchase-items', PurchaseItemViewSet, basename='purchase-item')

# Returns routes
router.register(r'sales-returns', SalesReturnViewSet, basename='sales-return')
router.register(r'purchase-returns', PurchaseReturnViewSet, basename='purchase-return')
router.register(r'bad-stocks', BadStockViewSet, basename='bad-stock')

router.register(r'accounts', AccountViewSet, basename='account')

urlpatterns = [
    path('', include(router.urls)),
    # path('login/', CustomLoginView.as_view(), name='custom-login'),
    path('auth/login/', CustomLoginView.as_view(), name='custom_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('pay-due/', DuePaymentAPIView.as_view(), name='pay_due'),
    path('reports/', include('reports.urls')),
    path('', include('expenses.urls')),  # <-- include your expenses app
    path('money-receipts/', MoneyReceiptCreateAPIView.as_view(), name='money_receipt_create'),  # <-- add this line

]

