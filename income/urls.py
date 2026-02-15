from django.urls import path
from .views import (
    IncomeListView,
    IncomeHeadListCreateView,
    IncomeHeadDetailView
)

urlpatterns = [
    path('incomes/', IncomeListView.as_view(), name='incomes'),
    path('income-heads/', IncomeHeadListCreateView.as_view(), name='income-heads-list-create'),
    path('income-heads/<int:pk>/', IncomeHeadDetailView.as_view(), name='income-heads-detail'),
]