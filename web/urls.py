from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('sales/', views.sales_list_view, name='sales'),
    path('money-receipts/', views.receipts_list_view, name='receipts'),
    path('money-receipts/new/', views.receipt_create_view, name='receipt_new'),
    path('purchases/', views.purchases_list_view, name='purchases'),
    path('purchases/new/', views.purchase_create_view, name='purchase_new'),
    path('m/<slug:slug>/', views.soon_view, name='soon'),
]
