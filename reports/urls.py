from django.urls import path
from .views import (
    SalesReportView, PurchaseReportView, ProfitLossReportView,
    PurchaseReturnReportView, SalesReturnReportView, TopSoldProductsReportView,
    LowStockReportView, BadStockReportView, StockReportView
)

urlpatterns = [
    path('sales/', SalesReportView.as_view(), name='sales-report'),
    path('purchase/', PurchaseReportView.as_view(), name='purchase-report'),
    path('profit-loss/', ProfitLossReportView.as_view(), name='profit-loss-report'),
    path('purchase-return/', PurchaseReturnReportView.as_view(), name='purchase-return-report'),
    path('sales-return/', SalesReturnReportView.as_view(), name='sales-return-report'),
    path('top-sold-products/', TopSoldProductsReportView.as_view(), name='top-sold-products-report'),
    path('low-stock/', LowStockReportView.as_view(), name='low-stock-report'),
    path('bad-stock/', BadStockReportView.as_view(), name='bad-stock-report'),
    path('stock/', StockReportView.as_view(), name='stock-report'),
]
