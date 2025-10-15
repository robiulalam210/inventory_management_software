from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core API
    path('api/', include('core.urls')),  # core handles all apps


     path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),

    path('brands/', views.brand_list, name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),

    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
]
