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
else:
    # cPanel এ আলাদা media সার্ভার নেই — পণ্যের ছবি / লোগো Django নিজেই দেয় (শুধু media ফোল্ডারের ভেতর থেকে)।
    # static (CSS/JS) দেয় whitenoise।
    from django.urls import re_path
    from django.views.static import serve as _serve
    urlpatterns += [re_path(r'^media/(?P<path>.*)$', _serve, {'document_root': settings.MEDIA_ROOT})]


# ভুল ঠিকানা / সার্ভার-error: অ্যাপ (/api/) পায় JSON, ব্রাউজার পায় সুন্দর পাতা (web/templates/404.html, 500.html)
from django.http import JsonResponse  # noqa: E402
from django.views import defaults as _defaults  # noqa: E402


def _api(request):
    return request.path.startswith('/api/')


def handler404(request, exception=None):
    if _api(request):
        return JsonResponse({'status': False, 'success': False, 'message': 'Not found.'}, status=404)
    return _defaults.page_not_found(request, exception)


def handler500(request):
    if _api(request):
        return JsonResponse({'status': False, 'success': False,
                             'message': 'Server error. Please try again shortly.'}, status=500)
    return _defaults.server_error(request)
