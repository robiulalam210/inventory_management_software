from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    return HttpResponse("✅ Health Check: Server is running perfectly!", status=200)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('shop/', include('shop.urls')),  # কাস্টমারের অনলাইন শপ (পাবলিক)
    path('api/', include('core.urls')),  # core app APIs
    path('', include('web.urls')),  # web software (browser থেকে — admin panel নয়)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
