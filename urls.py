# inventory_api/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Apps
    path('api/', include('products.urls')),
    path('api/branch/', include('branch_warehouse.urls')),
    path('api/', include('purchases.urls')),


    path('api/', include('suppliers.urls')),
    path('api/', include('customers.urls')),
    path('api/', include('purchases.urls')),
    path('api/', include('sales.urls')),

    # add additional app urls:
    # path('api/accounts/', include('accounts.urls')),
    # path('api/branches/', include('branches.urls')),
    # path('api/expenses/', include('expenses.urls')),
    # path('api/cheques/', include('cheques.urls')),
    # path('api/hr/', include('hr.urls')),
    # path('api/reports/', include('reports.urls')),
]
