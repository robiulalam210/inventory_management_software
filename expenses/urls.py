from django.urls import path
from .views import ExpenseHeadListView, ExpenseSubHeadListView, ExpenseListView

urlpatterns = [
    path('expense-heads/', ExpenseHeadListView.as_view(), name='expense-head-list'),
    path('expense-subheads/', ExpenseSubHeadListView.as_view(), name='expense-subhead-list'),
    path('expense/', ExpenseListView.as_view(), name='expense-list'),
]
