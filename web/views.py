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


def has_perm(user, module, action='view'):
    """app এর একই permission — user.get_permissions()"""
    perms = user.get_permissions() if hasattr(user, 'get_permissions') else {}
    return bool((perms.get(module) or {}).get(action))


def forbidden(request, title):
    return render(request, 'web/forbidden.html', {'page_title': title}, status=403)


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
    """
    My Dashboard — desktop app এর dashboard এর মতো: আজ/এই মাস/সব সময়ের বিক্রি, কেনা, খরচ, লাভ,
    টাকার প্রবাহ, account balance, সবচেয়ে বেশি বিক্রি, low stock, সাম্প্রতিক কাজ।
    কোন অংশ দেখাবে তা permission অনুযায়ী (যেমন Accounts দেখার অনুমতি না থাকলে balance দেখায় না)।
    Dashboard এর অনুমতি না থাকলে শুধু তার module গুলোর shortcut দেখায়।
    """
    perms = request.user.get_permissions()

    def can(module, action='view'):
        return bool((perms.get(module) or {}).get(action))

    now = timezone.localtime()
    greeting = 'Good morning' if now.hour < 12 else 'Good afternoon' if now.hour < 17 else 'Good evening'
    if can('dashboard'):
        return render(request, 'web/dashboard.html', {
            'page_title': 'My Dashboard',
            'greeting': greeting,
            'today': now,
            'dash_perms': {
                'accounts': can('accounts'),
                'reports': can('reports'),
                'sales': can('sales'),
                'purchases': can('purchases'),
                'expense': can('expense'),
            },
        })

    menu = build_menu(request.user, request.path)
    shortcuts = [
        {'title': item['title'], 'href': item['href'], 'ready': item['ready'], 'section': s['title'], 'icon': s['icon']}
        for s in menu
        for item in s['items']
        if s['title'] != 'Dashboard'
    ]
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


@web_login_required
@never_cache
def sales_list_view(request):
    """
    Sale List — সব বিক্রির তালিকা: search, তারিখ/অবস্থা/customer/বিক্রেতা filter, মোট হিসাব,
    আর যেকোনো invoice পাশে খুলে দেখা ও print।
    Data আসে app এর একই API থেকে: /api/sales/ আর /api/sales/summary/
    """
    if not has_perm(request.user, 'sales', 'view'):
        return forbidden(request, 'Sale List')
    return render(request, 'web/sales/list.html', {
        'page_title': 'Sale List',
        'can_see_users': has_perm(request.user, 'users', 'view'),
        'can_collect': has_perm(request.user, 'money_receipt', 'create'),
    })


@web_login_required
@never_cache
def receipts_list_view(request):
    """
    Money Receipt List — customer এর কাছ থেকে নেওয়া সব টাকার রসিদ: search, তারিখ/ধরন/customer/
    method filter, মোট হিসাব, রসিদ দেখা ও print, আর (অনুমতি থাকলে) রসিদ বাতিল।
    Data: /api/money-receipts/ আর /api/money-receipts/summary/
    """
    if not has_perm(request.user, 'money_receipt', 'view'):
        return forbidden(request, 'Money Receipt List')
    return render(request, 'web/receipts/list.html', {
        'page_title': 'Money Receipts',
        'can_create': has_perm(request.user, 'money_receipt', 'create'),
        'can_delete': has_perm(request.user, 'money_receipt', 'delete'),
        'can_see_users': has_perm(request.user, 'users', 'view'),
    })


@web_login_required
@never_cache
def receipt_create_view(request):
    """
    Create Money Receipt — customer বাছাই করলে তার বাকি invoice গুলো দেখায়; টাকা লিখলে আগেই দেখায়
    কোন invoice এ কত বসবে আর কত advance থাকবে (backend এর হুবহু একই নিয়মে)।
    ?customer=<id>&sale=<id> দিয়ে Sale List থেকে সরাসরি আসা যায়।
    """
    if not has_perm(request.user, 'money_receipt', 'create'):
        return forbidden(request, 'Create Money Receipt')

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    user = request.user
    return render(request, 'web/receipts/new.html', {
        'page_title': 'New Money Receipt',
        'form_init': {
            'customer': _int(request.GET.get('customer')),
            'sale': _int(request.GET.get('sale')),
            'me': {'id': user.id, 'name': user.get_full_name() or user.username},
            'canPickCollector': has_perm(user, 'users', 'view'),
            'canSeeList': has_perm(user, 'money_receipt', 'view'),
        },
    })


@web_login_required
@never_cache
def purchases_list_view(request):
    """
    Purchase List — supplier এর কাছ থেকে সব কেনা: search, তারিখ/অবস্থা/supplier filter, মোট হিসাব,
    invoice দেখা ও print, আর (অনুমতি থাকলে) বাতিল — বাতিলে stock আর দেওয়া টাকা দুটোই ফেরে।
    Data: /api/purchases/ আর /api/purchases/summary/
    """
    if not has_perm(request.user, 'purchases', 'view'):
        return forbidden(request, 'Purchase List')
    return render(request, 'web/purchases/list.html', {
        'page_title': 'Purchases',
        'can_create': has_perm(request.user, 'purchases', 'create'),
        'can_cancel': has_perm(request.user, 'purchases', 'delete'),
    })


@web_login_required
@never_cache
def purchase_create_view(request):
    """
    Create Purchase — supplier, পণ্য (নাম/SKU/barcode দিয়ে খুঁজে), দাম, ছাড়, VAT/চার্জ, আর চাইলে
    এখনই পরিশোধ। মোট হিসাব backend এর Purchase.update_totals() এর হুবহু একই নিয়মে আগেই দেখায়।
    """
    if not has_perm(request.user, 'purchases', 'create'):
        return forbidden(request, 'Create Purchase')
    return render(request, 'web/purchases/new.html', {
        'page_title': 'New Purchase',
        'form_init': {
            'supplier': request.GET.get('supplier') or '',
            'canSeeList': has_perm(request.user, 'purchases', 'view'),
        },
    })


@web_login_required
@never_cache
def suppliers_view(request):
    """
    Supplier List — সব supplier, কার কাছে কত বাকি/অগ্রিম, যোগ/সম্পাদনা, আর একজনের পুরো হিসাব
    (সাম্প্রতিক কেনা ও পরিশোধ) পাশে খুলে দেখা।
    """
    u = request.user
    if not has_perm(u, 'suppliers', 'view'):
        return forbidden(request, 'Supplier List')
    return render(request, 'web/suppliers/list.html', {
        'page_title': 'Suppliers',
        'sp_perms': {
            'create': has_perm(u, 'suppliers', 'create'),
            'edit': has_perm(u, 'suppliers', 'edit'),
            'delete': has_perm(u, 'suppliers', 'delete'),
            'pay': has_perm(u, 'suppliers', 'create'),
            'purchase': has_perm(u, 'purchases', 'create'),
            'purchases': has_perm(u, 'purchases', 'view'),
        },
    })


@web_login_required
@never_cache
def supplier_payments_view(request):
    """Supplier Payment — supplier কে দেওয়া সব টাকার voucher: filter, মোট, দেখা/print, বাতিল।"""
    u = request.user
    if not has_perm(u, 'suppliers', 'view'):
        return forbidden(request, 'Supplier Payments')
    return render(request, 'web/suppliers/payments.html', {
        'page_title': 'Supplier Payments',
        'can_create': has_perm(u, 'suppliers', 'create'),
        'can_cancel': has_perm(u, 'suppliers', 'delete'),
    })


@web_login_required
@never_cache
def supplier_payment_new_view(request):
    """
    নতুন Supplier Payment — supplier এর বাকি invoice দেখে, পুরনো আগে / একটা invoice / অগ্রিম —
    টাকা কোথায় বসবে আগেই দেখায় (backend এর একই নিয়মে)।
    """
    u = request.user
    if not has_perm(u, 'suppliers', 'create'):
        return forbidden(request, 'Pay Supplier')

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return render(request, 'web/suppliers/pay.html', {
        'page_title': 'Pay Supplier',
        'form_init': {
            'supplier': _int(request.GET.get('supplier')),
            'purchase': _int(request.GET.get('purchase')),
            'canSeeList': has_perm(u, 'suppliers', 'view'),
        },
    })


def _sell_init(request):
    """Sale আর POS দুটোর একই শুরুর তথ্য"""
    u = request.user
    return {
        'me': {'id': u.id, 'name': u.get_full_name() or u.username},
        'canPickSeller': has_perm(u, 'users', 'view'),
        'canSeeList': has_perm(u, 'sales', 'view'),
        'canCollect': has_perm(u, 'money_receipt', 'create'),
        'company': {
            'name': getattr(getattr(u, 'company', None), 'name', '') or '',
            'address': getattr(getattr(u, 'company', None), 'address', '') or '',
            'phone': getattr(getattr(u, 'company', None), 'phone', '') or '',
        },
    }


@web_login_required
@never_cache
def sale_new_view(request):
    """
    Sale — পূর্ণ বিক্রির form (app এর "Sale" screen এর মতো): customer, পণ্য খুঁজে যোগ, দাম/ছাড়,
    VAT/চার্জ, পরিশোধ ও বাকি। মোট হিসাব backend এর Sale.calculate_totals() এর একই নিয়মে।
    """
    if not has_perm(request.user, 'sales', 'create'):
        return forbidden(request, 'Sale')
    init = _sell_init(request)
    try:
        init['customer'] = int(request.GET.get('customer') or 0) or None
    except ValueError:
        init['customer'] = None
    return render(request, 'web/sales/new.html', {'page_title': 'New Sale', 'sell_init': init})


@web_login_required
@never_cache
def pos_view(request):
    """
    POS Sale — কাউন্টারের দ্রুত বিক্রি: পণ্যের grid, barcode scan, cart, নগদ নিয়ে ফেরত হিসাব,
    আর ছোট (80mm) রসিদ print।
    """
    if not has_perm(request.user, 'sales', 'create'):
        return forbidden(request, 'POS Sale')
    return render(request, 'web/sales/pos.html', {'page_title': 'POS', 'sell_init': _sell_init(request), 'pos_page': True})


@web_login_required
@never_cache
def customers_view(request):
    """
    Customers — সব customer, কার কাছে কত বাকি/অগ্রিম, যোগ/সম্পাদনা, আর একজনের পুরো হিসাব:
    সাম্প্রতিক বিক্রি, টাকা গ্রহণ, আর তারিখ ধরে statement (চলমান বাকি সহ, print করা যায়)।
    """
    u = request.user
    if not has_perm(u, 'customers', 'view'):
        return forbidden(request, 'Customers')
    return render(request, 'web/customers/list.html', {
        'page_title': 'Customers',
        'cu_perms': {
            'create': has_perm(u, 'customers', 'create'),
            'edit': has_perm(u, 'customers', 'edit'),
            'delete': has_perm(u, 'customers', 'delete'),
            'sell': has_perm(u, 'sales', 'create'),
            'sales': has_perm(u, 'sales', 'view'),
            'collect': has_perm(u, 'money_receipt', 'create'),
            'receipts': has_perm(u, 'money_receipt', 'view'),
            'statement': has_perm(u, 'reports', 'view'),
        },
    })
