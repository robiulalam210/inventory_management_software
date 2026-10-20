from django.urls import path

from .views import BranchCurrentView, BranchDetailView, BranchListView, BranchStockView, StockTransferView

urlpatterns = [
    path('branches/', BranchListView.as_view(), name='branch-list'),
    path('branches/current/', BranchCurrentView.as_view(), name='branch-current'),
    path('branches/<int:pk>/', BranchDetailView.as_view(), name='branch-detail'),
    path('branches/stock/', BranchStockView.as_view(), name='branch-stock'),
    path('branches/transfers/', StockTransferView.as_view(), name='branch-transfers'),
]
