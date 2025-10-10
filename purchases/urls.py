from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, PurchaseViewSet, PurchaseItemViewSet

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet)
router.register(r'purchases', PurchaseViewSet)
router.register(r'purchase-items', PurchaseItemViewSet)

urlpatterns = router.urls
