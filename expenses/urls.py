from django.urls import path
from .views import ExpenseHeadListView, ExpenseSubHeadListView, ExpenseListView, ExpenseHeadDetailView, ExpenseSubHeadDetailView, ExpenseDetailView

urlpatterns = [

    # path('expense-heads/', ExpenseHeadListView.as_view(), name='expense-heads'),
    # path('expense-heads/<int:pk>/', ExpenseHeadListView.as_view(), name='expense-head-detail'),

    # path('expense-subheads/', ExpenseSubHeadListView.as_view(), name='expense-subheads'),
    # path('expense-subheads/<int:pk>/', ExpenseSubHeadListView.as_view(), name='expense-subhead-detail'),

    # path('expenses/', ExpenseListView.as_view(), name='expenses'),
    # path('expenses/<int:pk>/', ExpenseListView.as_view(), name='expense-detail'),



     # Expense Head URLs
    path('expense-heads/', ExpenseHeadListView.as_view(), name='expense-head-list'),
    path('expense-heads/<int:pk>/', ExpenseHeadDetailView.as_view(), name='expense-head-detail'),
    
    # Expense SubHead URLs
    path('expense-subheads/', ExpenseSubHeadListView.as_view(), name='expense-subhead-list'),
    path('expense-subheads/<int:pk>/', ExpenseSubHeadDetailView.as_view(), name='expense-subhead-detail'),
    
    # Expense URLs
    path('expenses/', ExpenseListView.as_view(), name='expense-list'),
    path('expenses/<int:pk>/',ExpenseDetailView.as_view(), name='expense-detail'),
]
