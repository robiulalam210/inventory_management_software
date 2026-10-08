from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('sales/', views.sales_list_view, name='sales'),
    path('sales/new/', views.sale_new_view, name='sale_new'),
    path('pos/', views.pos_view, name='pos'),
    path('money-receipts/', views.receipts_list_view, name='receipts'),
    path('money-receipts/new/', views.receipt_create_view, name='receipt_new'),
    path('purchases/', views.purchases_list_view, name='purchases'),
    path('purchases/new/', views.purchase_create_view, name='purchase_new'),
    path('suppliers/', views.suppliers_view, name='suppliers'),
    path('customers/', views.customers_view, name='customers'),
    path('supplier-payments/', views.supplier_payments_view, name='supplier_payments'),
    path('supplier-payments/new/', views.supplier_payment_new_view, name='supplier_pay'),
    path('m/<slug:slug>/', views.soon_view, name='soon'),
]
