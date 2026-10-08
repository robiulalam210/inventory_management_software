from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('m/<slug:slug>/', views.soon_view, name='soon'),
]
