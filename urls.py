from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Apps (each app gets its own unique prefix)
    # path('api/products/', include('products.urls')),      # <--- products API
    # path('api/branch/', include('branch_warehouse.urls')),
    # path('api/purchases/', include('purchases.urls')),
    # path('api/suppliers/', include('suppliers.urls')),
    # path('api/customers/', include('customers.urls')),
    # path('api/sales/', include('sales.urls')),     # sales app routes
    # path('sales/pay-due/', DuePaymentAPIView.as_view(), name='pay_due'),

]
