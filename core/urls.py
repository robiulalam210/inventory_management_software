from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, AccountViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'accounts', AccountViewSet)

urlpatterns = [
    path('', include(router.urls)),
     path('api/products/', include('products.urls')),
    path('api/branch/', include('branch_warehouse.urls')),
]
