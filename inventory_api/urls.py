from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.shortcuts import render
from core.views import home
from django.conf import settings
from django.conf.urls.static import static

# def home(request):
#     return HttpResponse("""
#     <html>
#         <head><title>Django Server - Running Successfully</title></head>
#         <body style="font-family: Arial, sans-serif; margin: 40px;">
#             <h1>ðŸš€ Django Server is Working!</h1>
#             <p>Database connected successfully.</p>
#             <div style="margin-top: 20px;">
#                 <h3>Available Links:</h3>
#                 <ul>
#                     <li><a href="/admin/" style="color: blue;">Admin Panel</a></li>
#                     <li><a href="/health/" style="color: green;">Health Check</a></li>
#                 </ul>
#             </div>
#         </body>
#     </html>
#     """)

def health_check(request):
    return HttpResponse("âœ… Health Check: Server is running perfectly!", status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('', home, name='home'),
        path('api/', include('core.urls')),  # core app APIs

]
