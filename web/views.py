from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from . import auth
from .menu import build_menu, find_item

LOGIN_URL = reverse_lazy('web:login')

# "আমাকে মনে রাখো" দিলে ৭ দিন (app এর refresh token এর সমান), না দিলে browser বন্ধ হলেই শেষ
REMEMBER_SECONDS = 7 * 24 * 60 * 60


def web_login_required(view):
    return login_required(view, login_url=LOGIN_URL)


def _safe_next(request, fallback):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and nxt.startswith('/app/') and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return fallback


@sensitive_post_parameters('password')
@csrf_protect
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, reverse('web:home')))

    ctx = {
        'identifier': '',
        'remember': True,
        'next': request.GET.get('next', ''),
        'error': None,
    }

    if request.method == 'POST':
        identifier = (request.POST.get('identifier') or '').strip()
        password = request.POST.get('password') or ''
        remember = request.POST.get('remember') == 'on'
        ctx.update(identifier=identifier, remember=remember, next=request.POST.get('next', ''))

        if not identifier or not password:
            ctx['error'] = 'Enter your username or email and your password.'
            return render(request, 'web/auth/login.html', ctx, status=400)

        wait = auth.locked_minutes(request, identifier)
        if wait:
            ctx['error'] = f'Too many failed attempts. Please try again in {wait} minute{"s" if wait != 1 else ""}.'
            ctx['locked'] = True
            return render(request, 'web/auth/login.html', ctx, status=429)

        user, error = auth.authenticate_identifier(identifier, password)
        if user is None:
            left = auth.register_failure(request, identifier)
            if left <= 0:
                # এই ভুলেই সীমা পূর্ণ — সাথে সাথে জানানো, পরের চেষ্টায় নয়
                ctx['error'] = 'Too many failed attempts. Sign-in is paused for 15 minutes.'
                ctx['locked'] = True
                return render(request, 'web/auth/login.html', ctx, status=429)
            ctx['error'] = error or 'Invalid credentials'
            if left <= 2:
                ctx['warning'] = f'{left} attempt{"s" if left != 1 else ""} left before sign-in is paused for 15 minutes.'
            return render(request, 'web/auth/login.html', ctx, status=401)

        auth.clear_failures(request, identifier)
        login(request, user)  # session id নতুন করে তৈরি হয় (session fixation ঠেকাতে)
        request.session.set_expiry(REMEMBER_SECONDS if remember else 0)
        request.session['web_client'] = 'web'
        return redirect(_safe_next(request, reverse('web:home')))

    if request.GET.get('expired'):
        ctx['info'] = 'Your session has ended. Please sign in again.'
    return render(request, 'web/auth/login.html', ctx)


@require_POST
@csrf_protect
def logout_view(request):
    name = ''
    if request.user.is_authenticated:
        name = (getattr(request.user, 'full_name', '') or '').strip() or request.user.username
    logout(request)  # পুরো session মুছে যায়
    messages.success(request, f'Signed out{" — see you soon, " + name if name else ""}.')
    return redirect('web:login')


@web_login_required
@never_cache
def home_view(request):
    menu = build_menu(request.user, request.path)
    shortcuts = [
        {'title': item['title'], 'href': item['href'], 'ready': item['ready'], 'section': s['title'], 'icon': s['icon']}
        for s in menu
        for item in s['items']
        if s['title'] != 'Dashboard'
    ]
    now = timezone.localtime()
    greeting = 'Good morning' if now.hour < 12 else 'Good afternoon' if now.hour < 17 else 'Good evening'
    return render(request, 'web/home.html', {
        'page_title': 'My Dashboard',
        'greeting': greeting,
        'today': now,
        'shortcuts': shortcuts[:12],
        'module_count': len(shortcuts),
    })


@web_login_required
@never_cache
def soon_view(request, slug):
    """এখনো তৈরি হয়নি এমন module — menu থেকে ক্লিক করলে জানায়"""
    section, item = find_item(slug)
    if not item:
        raise Http404
    # permission নেই এমন module এর পাতায় সরাসরি ঢোকা যাবে না
    allowed = any(i['slug'] == slug for s in build_menu(request.user) for i in s['items'])
    if not allowed:
        return render(request, 'web/forbidden.html', {'page_title': item['title']}, status=403)
    return render(request, 'web/soon.html', {
        'page_title': item['title'],
        'section_title': section['title'],
        'section_icon': section['icon'],
    })
