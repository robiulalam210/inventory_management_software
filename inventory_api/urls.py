from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.shortcuts import render

def home(request):
      return render(request, 'home.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),  # core app APIs
    path('', home),  # This will handle the root URL
]