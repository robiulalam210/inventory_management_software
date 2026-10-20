from django.urls import path

from . import views as v

urlpatterns = [
    path('stock/adjustments/', v.StockAdjustmentView.as_view(), name='stock-adjustments'),
    path('stock/counts/', v.StocktakeListView.as_view(), name='stock-counts'),
    path('stock/counts/<int:pk>/', v.StocktakeDetailView.as_view(), name='stock-count-detail'),
    path('stock/counts/<int:pk>/count/', v.StocktakeCountView.as_view(), name='stock-count-save'),
    path('stock/counts/<int:pk>/apply/', v.StocktakeApplyView.as_view(), name='stock-count-apply'),
    path('stock/counts/<int:pk>/cancel/', v.StocktakeCancelView.as_view(), name='stock-count-cancel'),
    path('day-close/summary/', v.DayCloseSummaryView.as_view(), name='day-close-summary'),
    path('day-close/', v.DayCloseListView.as_view(), name='day-close'),
    path('day-close/<int:pk>/', v.DayCloseDetailView.as_view(), name='day-close-detail'),
]
