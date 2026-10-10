from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('<int:company_id>/', views.store_view, name='store'),
    path('<int:company_id>/order/', views.place_order_view, name='place_order'),
]
