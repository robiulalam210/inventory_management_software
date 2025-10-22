from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomLoginView, CompanyViewSet, UserViewSet, StaffRoleViewSet, StaffViewSet, CustomTokenObtainPairView, 
    company_admin_signup, company_admin_login, dashboard, user_list, create_user, home, user_management
)
from rest_framework_simplejwt.views import TokenRefreshView
from money_receipts.views import MoneyReceiptCreateAPIView
from supplier_payment.view import SupplierPaymentListCreateAPIView, SupplierPaymentDetailAPIView
from purchases.views import PurchaseViewSet, PurchaseItemViewSet,get_due_purchases
from purchases.views import get_due_purchases
from suppliers.views import SupplierViewSet
from sales.views import SaleViewSet, SaleItemViewSet,get_due_sales  # Import get_due_sales here
from sales.views import SaleViewSet, SaleItemViewSet    
from customers.views import CustomerViewSet
from products.views import ProductViewSet, CategoryViewSet, UnitViewSet, BrandViewSet, GroupViewSet, SourceViewSet
from returns.views import SalesReturnViewSet, PurchaseReturnViewSet, BadStockViewSet
from accounts.views import AccountViewSet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from core.froms import CompanyAdminSignupForm, UserForm
# Remove this import since we're importing functions directly above
# from . import views

router = DefaultRouter()

router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'users', UserViewSet, basename='user')
router.register(r'staff-roles', StaffRoleViewSet, basename='staffrole')
router.register(r'staffs', StaffViewSet, basename='staff')

router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'units', UnitViewSet, basename='unit')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'sale-items', SaleItemViewSet, basename='sale-item')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchases', PurchaseViewSet, basename='purchase')
router.register(r'purchase-items', PurchaseItemViewSet, basename='purchase-item')
router.register(r'sales-returns', SalesReturnViewSet, basename='sales-return')
router.register(r'purchase-returns', PurchaseReturnViewSet, basename='purchase-return')
router.register(r'bad-stocks', BadStockViewSet, basename='bad-stock')
router.register(r'accounts', AccountViewSet, basename='account')

urlpatterns = [
    # API routes
    path('', include(router.urls)),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/login/', CustomLoginView.as_view(), name='custom_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('money-receipts/', MoneyReceiptCreateAPIView.as_view(), name='money_receipt_create'),
    path('supplier-payments/', SupplierPaymentListCreateAPIView.as_view(), name='supplier-payment-list-create'),
    path('supplier-payments/<int:pk>/', SupplierPaymentDetailAPIView.as_view(), name='supplier-payment-detail'),

    path('reports/', include('reports.urls')),

    path('expenses/', include('expenses.urls')),
    
    # FIXED: Use the imported function directly, not via views.
    path('due/', get_due_sales, name='due-sales'),  # This creates /api/due/
    path('purchase-due/', get_due_purchases, name='get_due_purchases'),

    # Custom API endpoints for stock filtering
    path('api/products/search/', ProductViewSet.as_view({'get': 'search'}), name='product-search'),
    path('api/products/stock-info/', ProductViewSet.as_view({'get': 'stock_info'}), name='product-stock-info'),
    path('api/products/low-stock/', ProductViewSet.as_view({'get': 'low_stock'}), name='product-low-stock'),
    path('api/products/advanced-search/', ProductViewSet.as_view({'get': 'advanced_search'}), name='product-advanced-search'),
    path('api/products/filters/', ProductViewSet.as_view({'get': 'filters'}), name='product-filters'),
# GET /api/products/stock-info/?status=0  # Out of stock
# GET /api/products/stock-info/?status=1  # Low stock  
# GET /api/products/stock-info/?status=2  # In stock

# GET /api/products/?stock_status=0  # Using filter class
# GET /api/products/?stock_status=1  # Using filter class
# GET /api/products/?stock_status=2  # Using filter class
# GET /api/products/?category=1&stock_status=1&product_name=laptop
# GET /api/products/search/?q=laptop&category_id=1&stock_status=2
# GET /api/products/low-stock/  # Only low stock products

    # Admin UI
    path('admin/signup/', company_admin_signup, name='company_admin_signup'),
    path('admin/login/', company_admin_login, name='company_admin_login'),
    path('admin/dashboard/', dashboard, name='admin_dashboard'),
    path('admin/users/', user_list, name='user_list'),
    path('admin/users/create/', create_user, name='create_user'),
]