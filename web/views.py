from django.conf import settings
from django.contrib import messages
from datetime import date, timedelta

from django.contrib.auth import login, logout
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
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


def is_platform_admin(user):
    return bool(user and user.is_authenticated and (getattr(user, 'role', '') == 'SUPER_ADMIN' or user.is_superuser))


def company_blocked(user):
    """কোম্পানি বন্ধ (suspended) থাকলে তার কেউ web এ ঢুকতে পারে না — super admin বাদে"""
    company = getattr(user, 'company', None)
    return bool(company is not None and not company.is_active and not is_platform_admin(user))


# কোম্পানি-হীন Super Admin যে পেজগুলোতে ঢুকতে পারে
PLATFORM_VIEWS = {'home_view', 'platform_companies_view', 'audit_log_view', 'view_company_view', 'exit_company_view'}


def web_login_required(view):
    from functools import wraps

    @wraps(view)
    def inner(request, *args, **kwargs):
        if request.user.is_authenticated and company_blocked(request.user):
            logout(request)
            return redirect(reverse('web:login') + '?suspended=1')
        # কোম্পানি-হীন Super Admin এর দোকানের কোনো পেজ (sale, product, unit...) নেই — সরাসরি URL এ গেলেও Companies এ ফেরত
        if (request.user.is_authenticated and is_platform_admin(request.user)
                and not getattr(request.user, 'company_id', None)
                and getattr(view, '__name__', '') not in PLATFORM_VIEWS):
            return redirect('web:platform_companies')
        return view(request, *args, **kwargs)
    return login_required(inner, login_url=LOGIN_URL)


def has_perm(user, module, action='view'):
    """app এর একই permission — user.get_permissions()"""
    perms = user.get_permissions() if hasattr(user, 'get_permissions') else {}
    return bool((perms.get(module) or {}).get(action))


def forbidden(request, title):
    return render(request, 'web/forbidden.html', {'page_title': title}, status=403)


def _safe_next(request, fallback):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and nxt.startswith('/') and not nxt.startswith('//') and url_has_allowed_host_and_scheme(
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

        if company_blocked(user):
            ctx['error'] = (f'{user.company.name} is suspended, so nobody from it can sign in right now. '
                            'Please contact your software provider.')
            return render(request, 'web/auth/login.html', ctx, status=403)

        auth.clear_failures(request, identifier)
        login(request, user)  # session id নতুন করে তৈরি হয় (session fixation ঠেকাতে)
        request.session.set_expiry(REMEMBER_SECONDS if remember else 0)
        request.session['web_client'] = 'web'
        return redirect(_safe_next(request, reverse('web:home')))

    if request.GET.get('expired'):
        ctx['info'] = 'Your session has ended. Please sign in again.'
    if request.GET.get('suspended'):
        ctx['error'] = 'Your company has been suspended. Please contact your software provider.'
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
    # Super admin এর কোনো দোকান নেই — তার কাজ কোম্পানি চালানো
    if is_platform_admin(request.user) and not getattr(request.user, 'company', None):
        return redirect('web:platform_companies')
    perms = request.user.get_permissions()

    def can(module, action='view'):
        return bool((perms.get(module) or {}).get(action))

    now = timezone.localtime()
    greeting = 'Good morning' if now.hour < 12 else 'Good afternoon' if now.hour < 17 else 'Good evening'
    if can('dashboard'):
        shop_ctx = {}
        company = getattr(request.user, 'company', None)
        if company is not None and can('sales'):
            from shop.models import ShopOrder, ShopSettings
            shop_ctx = {
                'shop_url': ShopSettings.for_company(company).public_url(request),
                'shop_pending': ShopOrder.objects.filter(company=company, status='pending').count(),
            }
        return render(request, 'web/dashboard.html', {
            **shop_ctx,
            'page_title': 'My Dashboard',
            'greeting': greeting,
            'today': now,
            'dash_perms': {
                'accounts': can('accounts'),
                'reports': can('reports'),
                'sales': can('sales'),
                'purchases': can('purchases'),
                'expense': can('expense'),
                'customers': can('customers'),
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
def short_sale_view(request):
    """
    Short Sale — app এর "Short Sale" এর মতো: ক্যাটাগরি → পণ্য → সেল মোড (কেজি/গ্রাম/প্যাক) → পরিমাণ → Add।
    এরপর customer, ছাড়/চার্জ ও পেমেন্ট Sale ফর্মের মতোই; সেভ হয় একই /api/sales/ এ।
    """
    if not has_perm(request.user, 'sales', 'create'):
        return forbidden(request, 'Short Sale')
    init = _sell_init(request)
    init['customer'] = None
    return render(request, 'web/sales/short.html', {'page_title': 'Short Sale', 'sell_init': init})


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


@web_login_required
@never_cache
def products_view(request):
    """
    Products — সব পণ্য: stock অবস্থা (যথেষ্ট / কম / শেষ), দাম ও লাভের হার, যোগ/সম্পাদনা (ছবি সহ),
    আর SKU এর barcode label print — POS এ scan করার জন্য।
    """
    u = request.user
    if not has_perm(u, 'products', 'view'):
        return forbidden(request, 'Products')
    return render(request, 'web/products/list.html', {
        'page_title': 'Products',
        'pr_perms': {
            'create': has_perm(u, 'products', 'create'),
            'edit': has_perm(u, 'products', 'edit'),
            'delete': has_perm(u, 'products', 'delete'),
            'buy': has_perm(u, 'purchases', 'create'),
            'reports': has_perm(u, 'reports', 'view'),
        },
    })


@web_login_required
@never_cache
def accounts_view(request):
    """
    Accounts — Cash / Bank / Mobile banking এর balance, আর প্রতিটা account এর statement (কোন টাকা কবে
    এল-গেল, প্রতিটার পরে balance)। হিসাব না মিললে সেটাও দেখায়।
    """
    u = request.user
    if not has_perm(u, 'accounts', 'view'):
        return forbidden(request, 'Accounts')
    return render(request, 'web/accounts/list.html', {
        'page_title': 'Accounts',
        'ac_perms': {
            'create': has_perm(u, 'accounts', 'create'),
            'edit': has_perm(u, 'accounts', 'edit'),
            'delete': has_perm(u, 'accounts', 'delete'),
        },
    })


@web_login_required
@never_cache
def units_view(request):
    """
    Units — product কোন মাপে বিক্রি হয় (Pcs, Kg, Litre…)। Unit ছাড়া product তৈরি হয় না, তাই নতুন
    কোম্পানির জন্য এক ক্লিকে সাধারণ unit গুলো যোগ করার ব্যবস্থাও আছে।
    """
    u = request.user
    if not has_perm(u, 'administration', 'view'):
        return forbidden(request, 'Units')
    return render(request, 'web/admin/units.html', {
        'page_title': 'Units',
        'un_perms': {
            'create': has_perm(u, 'administration', 'create'),
            'edit': has_perm(u, 'administration', 'edit'),
            'delete': has_perm(u, 'administration', 'delete'),
        },
    })


@web_login_required
@never_cache
def platform_companies_view(request):
    """
    Companies (Super Admin) — সব কোম্পানি, নতুন কোম্পানি + তার এডমিন একবারে খোলা, প্ল্যান/মেয়াদ/limit,
    বন্ধ/চালু, এডমিনের password বদলানো। কোম্পানির নিজের admin এই page দেখতে পায় না।
    """
    if not is_platform_admin(request.user):
        return forbidden(request, 'Companies')
    from core.models import Company
    return render(request, 'web/platform/companies.html', {
        'page_title': 'Companies',
        'pf_plans': [{'value': v, 'label': l} for v, l in Company.PlanType.choices],
    })


def _team_page(request, title, start):
    u = request.user
    from core.team import is_admin
    return render(request, 'web/admin/staff.html', {
        'page_title': title,
        'tm_init': {
            'start': start,
            'perms': {
                'create': has_perm(u, 'users', 'create'),
                'edit': has_perm(u, 'users', 'edit'),
                'delete': has_perm(u, 'users', 'delete'),
            },
            'is_admin': is_admin(u),
            'me': u.id,
            # শাখা: ২+ শাখা থাকলেই স্টাফকে শাখায় বসানোর ঘর দেখায় (core/branches.py)
            'branches': _branch_choices(u),
        },
    })


def _branch_choices(u):
    from core.branches import active_count
    company = getattr(u, 'company', None)
    if company is None or active_count(company) < 2:
        return []
    from branch_warehouse.models import Branch
    return [{'id': b.id, 'name': b.name, 'is_main': b.is_main} for b in Branch.objects.filter(company=company, is_active=True)]


@web_login_required
@never_cache
def staff_view(request):
    """
    Staff — কোম্পানির মানুষ: কে login করতে পারে, কোন role, শেষ কবে এসেছে। নতুন মানুষ যোগ, role বদল,
    password বদল, বন্ধ/চালু। মুছে ফেলা হয় না — তাদের করা বিক্রি/রসিদে নাম থেকে যায়।
    """
    if not has_perm(request.user, 'users', 'view'):
        return forbidden(request, 'Staff')
    return _team_page(request, 'Staff', 'people')


@web_login_required
@never_cache
def user_permissions_view(request):
    """
    User Permissions — প্রত্যেকে কোন module এ কী করতে পারবে (দেখা / তৈরি / বদল / মোছা)।
    শুধু Admin; Admin দের নিজেদের সব থাকে, তাই তাদের বদলানো যায় না।
    """
    from core.team import is_admin
    if not is_admin(request.user):
        return forbidden(request, 'User Permissions')
    return _team_page(request, 'User Permissions', 'access')


@web_login_required
@never_cache
def company_profile_view(request):
    """
    Company Profile — দোকানের নাম, logo, ঠিকানা, ফোন: invoice আর রসিদের মাথায় যা ছাপা হয়।
    Plan, মেয়াদ, user limit শুধু দেখা যায় — ওগুলো Super Admin বদলান।
    """
    u = request.user
    if not has_perm(u, 'administration', 'view'):
        return forbidden(request, 'Company Profile')
    if not getattr(u, 'company', None):
        return redirect('web:home')
    return render(request, 'web/admin/profile.html', {
        'page_title': 'Company Profile',
        'cp_init': {'id': u.company_id, 'can_edit': has_perm(u, 'administration', 'edit')},
    })


# Category / Brand / Group / Source — একই রকম ছোট তালিকা, একটাই template (web/admin/lookup.html)
LOOKUPS = {
    'categories': {
        'title': 'Categories', 'singular': 'category', 'plural': 'categories', 'api': '/api/categories/',
        'icon': 'box', 'has_description': True, 'filter_param': 'category',
        'explain': 'Group products by type so they are easy to find on the sale and POS screens, and so reports can show what sells best.',
        'examples': ['Groceries', 'Beverages', 'Snacks', 'Personal care', 'Household', 'Electronics'],
    },
    'brands': {
        'title': 'Brands', 'singular': 'brand', 'plural': 'brands', 'api': '/api/brands/',
        'icon': 'sparkle', 'has_description': False, 'filter_param': '',
        'explain': 'Who makes the product. Lets you search and report by brand.',
        'examples': [],
    },
    'groups': {
        'title': 'Groups', 'singular': 'group', 'plural': 'groups', 'api': '/api/groups/',
        'icon': 'store', 'has_description': False, 'filter_param': '',
        'explain': 'Your own way of grouping products beyond category — for example fast-moving, seasonal or wholesale items.',
        'examples': ['Fast moving', 'Seasonal', 'Wholesale', 'Slow moving'],
    },
    'sources': {
        'title': 'Sources', 'singular': 'source', 'plural': 'sources', 'api': '/api/sources/',
        'icon': 'globe', 'has_description': False, 'filter_param': '',
        'explain': 'Where a product comes from — local market, imported, or made by you.',
        'examples': ['Local', 'Imported', 'Own production'],
    },
}


def _lookup_view(kind):
    cfg = LOOKUPS[kind]

    @web_login_required
    @never_cache
    def view(request):
        u = request.user
        if not has_perm(u, 'administration', 'view'):
            return forbidden(request, cfg['title'])
        lk = dict(cfg)
        lk['singular_title'] = cfg['singular'].capitalize()
        lk['perms'] = {
            # product তৈরির অনুমতি থাকলেও যোগ করা যায় (backend এর নিয়মের সাথে মিল রেখে)
            'create': has_perm(u, 'administration', 'create') or has_perm(u, 'products', 'create'),
            'edit': has_perm(u, 'administration', 'edit'),
            'delete': has_perm(u, 'administration', 'delete'),
        }
        return render(request, 'web/admin/lookup.html', {'page_title': cfg['title'], 'lk': lk})
    view.__name__ = f'{kind}_view'
    return view


categories_view = _lookup_view('categories')
brands_view = _lookup_view('brands')
groups_view = _lookup_view('groups')
sources_view = _lookup_view('sources')


@web_login_required
@never_cache
def sale_modes_view(request):
    """
    Sale Mode — একই product ভিন্ন মাপে বিক্রি (Gram/KG, Piece/Dozen, বস্তা)। Stock সবসময় product এর
    নিজের unit এ থাকে; sale mode বলে একবার বিক্রিতে কতটা কমবে, আর দাম কীভাবে হবে।
    """
    u = request.user
    if not has_perm(u, 'administration', 'view'):
        return forbidden(request, 'Sale Modes')
    return render(request, 'web/admin/salemodes.html', {
        'page_title': 'Sale Modes',
        'sm_perms': {
            'create': has_perm(u, 'administration', 'create') or has_perm(u, 'products', 'create'),
            'edit': has_perm(u, 'administration', 'edit'),
            'delete': has_perm(u, 'administration', 'delete'),
        },
    })


# ───────────── Expense / Income ─────────────
# খরচ: Expense module এর অনুমতি। আয়: Accounts module এর অনুমতি (menu তেও তাই)।
def _money_perms(u, module):
    return {a: has_perm(u, module, a) for a in ('create', 'edit', 'delete')}


@web_login_required
@never_cache
def expenses_view(request):
    """Expense List — দোকান চালাতে যা খরচ হয় (ভাড়া, বিল, বেতন…); কোন account থেকে গেল, খাত অনুযায়ী মোট"""
    u = request.user
    if not has_perm(u, 'expense', 'view'):
        return forbidden(request, 'Expenses')
    perms = _money_perms(u, 'expense')
    return render(request, 'web/money/ledger.html', {'page_title': 'Expenses', 'lg': {
        'kind': 'expense', 'noun': 'expense', 'plural': 'expenses', 'ref_label': 'EXP no.', 'icon': 'expense',
        'api': '/api/expenses/expenses/', 'summary_api': '/api/expenses/expenses/summary/',
        'heads_api': '/api/expenses/expense-heads/', 'subheads_api': '/api/expenses/expense-subheads/',
        'perms': perms, 'can_add_head': perms['create'],
        'empty_text': 'Record rent, bills, wages and other running costs. The money comes out of the account you pick, and profit reports count it.',
    }})


@web_login_required
@never_cache
def incomes_view(request):
    """Income List — বিক্রি ছাড়া অন্য আয় (ভাড়া পাওয়া, কমিশন…); কোন account এ এল"""
    u = request.user
    if not has_perm(u, 'accounts', 'view'):
        return forbidden(request, 'Income')
    perms = _money_perms(u, 'accounts')
    return render(request, 'web/money/ledger.html', {'page_title': 'Income', 'lg': {
        'kind': 'income', 'noun': 'income', 'plural': 'income entries', 'ref_label': 'INC no.', 'icon': 'income',
        'api': '/api/income/incomes/', 'summary_api': '/api/income/incomes/summary/',
        'heads_api': '/api/income/income-heads/', 'subheads_api': '',
        'perms': perms, 'can_add_head': perms['create'],
        'empty_text': 'Money that comes in other than sales — rent you receive, commission, a refund. It goes into the account you pick.',
    }})


def _heads_page(request, kind, title, focus_sub=False):
    u = request.user
    module = 'expense' if kind == 'expense' else 'accounts'
    if not has_perm(u, module, 'view'):
        return forbidden(request, title)
    exp = kind == 'expense'
    return render(request, 'web/money/heads.html', {'page_title': title, 'hd': {
        'kind': kind, 'icon': 'expense' if exp else 'income', 'focus_sub': focus_sub,
        'heads_api': '/api/expenses/expense-heads/' if exp else '/api/income/income-heads/',
        'subheads_api': '/api/expenses/expense-subheads/' if exp else '',
        'list_url': reverse('web:expenses') if exp else reverse('web:incomes'),
        'perms': _money_perms(u, module),
        'explain': ('What your money is spent on. Use sub heads to split a head further — Utilities › Electricity, Water, Internet.'
                    if exp else 'Where extra money comes from — anything other than sales.'),
        'empty_text': ('Add heads like Rent, Utilities, Salaries, Transport. Every expense is filed under one, so you can see where money goes.'
                       if exp else 'Add heads like Rent received, Commission or Interest.'),
    }})


@web_login_required
@never_cache
def expense_heads_view(request):
    return _heads_page(request, 'expense', 'Expense Heads')


@web_login_required
@never_cache
def expense_subheads_view(request):
    return _heads_page(request, 'expense', 'Expense Sub Heads', focus_sub=True)


@web_login_required
@never_cache
def income_heads_view(request):
    return _heads_page(request, 'income', 'Income Heads')


RETURN_KINDS = {
    'sales': {
        'kind': 'sales', 'noun': 'sales', 'new_url': 'web:sales_return_new',
        'no_label': 'Receipt', 'party_label': 'Customer', 'party_all': 'All customers',
        'refund_label': 'Refunded via', 'empty_hint': 'Goods customers send back will appear here.',
    },
    'purchase': {
        'kind': 'purchase', 'noun': 'purchase', 'new_url': 'web:purchase_return_new',
        'no_label': 'Invoice', 'party_label': 'Supplier', 'party_all': 'All suppliers',
        'refund_label': 'Refund received via', 'empty_hint': 'Goods you send back to suppliers will appear here.',
    },
}


def _returns_list(request, kind, title):
    if not has_perm(request.user, 'return', 'view'):
        return forbidden(request, title)
    return render(request, 'web/returns/list.html', {
        'page_title': title,
        'rt': RETURN_KINDS[kind],
        'can_create': has_perm(request.user, 'return', 'create'),
        'can_update': has_perm(request.user, 'return', 'edit'),
        'can_delete': has_perm(request.user, 'return', 'delete'),
    })


@web_login_required
@never_cache
def sales_returns_view(request):
    """
    Sales Return List — বিক্রি ফেরতের তালিকা: search, তারিখ/অবস্থা/customer filter, দেখা ও print, এবং অনুমতি
    থাকলে Approve / Reject / Complete / Delete (app এর একই নিয়ম: pending → approved → completed)।
    Data: /api/sales-returns/
    """
    return _returns_list(request, 'sales', 'Sales Returns')


@web_login_required
@never_cache
def purchase_returns_view(request):
    """Purchase Return List — supplier কে ফেরত পাঠানো মালের তালিকা। Data: /api/purchase-returns/ (workflow একই)"""
    return _returns_list(request, 'purchase', 'Purchase Returns')


@web_login_required
@never_cache
def sales_return_new_view(request):
    """Create Sales Return — invoice বাছলে তার পণ্যগুলো আসে; কত ফেরত ও কত নষ্ট (damage) লেখা যায়।"""
    if not has_perm(request.user, 'return', 'create'):
        return forbidden(request, 'Create Sales Return')
    return render(request, 'web/returns/sales_new.html', {
        'page_title': 'New Sales Return',
        'form_init': {
            'invoice': request.GET.get('invoice') or '',
            'canSeeList': has_perm(request.user, 'return', 'view'),
            'canApprove': has_perm(request.user, 'return', 'edit'),
        },
    })


@web_login_required
@never_cache
def purchase_return_new_view(request):
    """Create Purchase Return — supplier বাছলে তার invoice আসে, invoice বাছলে পণ্য আসে।"""
    if not has_perm(request.user, 'return', 'create'):
        return forbidden(request, 'Create Purchase Return')
    return render(request, 'web/returns/purchase_new.html', {
        'page_title': 'New Purchase Return',
        'form_init': {'canSeeList': has_perm(request.user, 'return', 'view')},
    })


@web_login_required
@never_cache
def bad_stock_view(request):
    """Bad Stock List — নষ্ট/ক্ষতিগ্রস্ত মালের হিসাব (Sales Return এ damage দিলে এখানে আসে)। Data: /api/bad-stocks/"""
    if not has_perm(request.user, 'return', 'view'):
        return forbidden(request, 'Bad Stock')
    return render(request, 'web/returns/bad_stock.html', {'page_title': 'Bad Stock'})


@web_login_required
@never_cache
def transfer_new_view(request):
    """
    Account Transfer — এক account থেকে আরেক account এ টাকা। "Quick transfer" চালু থাকলে সাথে সাথে টাকা সরে;
    বন্ধ থাকলে pending থাকে, পরে Transfer List থেকে execute করতে হয়। Data: /api/transfers/
    """
    if not has_perm(request.user, 'accounts', 'create'):
        return forbidden(request, 'Account Transfer')
    return render(request, 'web/transfers/new.html', {
        'page_title': 'Account Transfer',
        'form_init': {'canSeeList': has_perm(request.user, 'accounts', 'view')},
    })


@web_login_required
@never_cache
def transfers_view(request):
    """Transfer List — সব transfer; pending এ Execute / Cancel, completed এ Reverse (app এর একই নিয়ম)।"""
    u = request.user
    if not has_perm(u, 'accounts', 'view'):
        return forbidden(request, 'Transfer List')
    return render(request, 'web/transfers/list.html', {
        'page_title': 'Transfers',
        'can_create': has_perm(u, 'accounts', 'create'),
        'list_init': {'canEdit': has_perm(u, 'accounts', 'edit'), 'me': {'id': u.id}},
    })


@web_login_required
@never_cache
def transactions_view(request):
    """Transactions — সব account এর লেনদেন (শুধু দেখা): sale, receipt, purchase, expense, transfer। Data: /api/transactions/"""
    if not has_perm(request.user, 'accounts', 'view'):
        return forbidden(request, 'Transactions')
    return render(request, 'web/transfers/transactions.html', {'page_title': 'Transactions'})


@web_login_required
@never_cache
def audit_log_view(request):
    """
    Audit Log — কে, কখন, কোন app/device থেকে, কোন record এ কী বদলেছে (আগে/পরে)। শুধু দেখা।
    Super Admin ও Admin ছাড়া কেউ দেখে না — API ও একই নিয়ম মানে। Data: /api/sync/audit/ আর /api/sync/audit/meta/
    """
    u = request.user
    role = (getattr(u, 'role', '') or '').upper()
    if not (u.is_superuser or role in ('SUPER_ADMIN', 'ADMIN')):
        return forbidden(request, 'Audit Log')
    return render(request, 'web/security/audit.html', {'page_title': 'Audit Log'})


REPORT_TITLES = {
    'sales': 'Sales Report', 'purchases': 'Purchase Report', 'profit-loss': 'Profit / Loss',
    'top-products': 'Top Selling Products', 'low-stock': 'Low Stock', 'stock': 'Stock Report',
    'customer-ledger': 'Customer Ledger', 'customer-due': 'Customer Due / Advance',
    'supplier-ledger': 'Supplier Ledger', 'supplier-due': 'Supplier Due / Advance', 'expenses': 'Expense Report',
}


@web_login_required
@never_cache
def report_view(request, key):
    """সব report একই page — কোনটা, তা `key` ঠিক করে (web/static/web/js/reports.js এর REPORTS)।"""
    if not has_perm(request.user, 'reports', 'view'):
        return forbidden(request, 'Reports')
    return render(request, 'web/reports/report.html', {'page_title': REPORT_TITLES[key], 'key': key})


def _payroll_guard(request):
    u = request.user
    role = (getattr(u, 'role', '') or '').upper()
    return None if (u.is_superuser or role in ('SUPER_ADMIN', 'ADMIN') or has_perm(u, 'payroll', 'view')) else forbidden(request, 'Payroll')


@web_login_required
@never_cache
def payroll_view(request):
    """Salary Sheet — মাসের বেতন স্লিপ, pay, payslip। শুধু Admin / Super Admin (API ও একই নিয়ম)।"""
    return _payroll_guard(request) or render(request, 'web/payroll/sheet.html', {'page_title': 'Salary Sheet'})


@web_login_required
@never_cache
def payroll_advances_view(request):
    return _payroll_guard(request) or render(request, 'web/payroll/advances.html', {'page_title': 'Salary Advances'})


@web_login_required
@never_cache
def payroll_report_view(request):
    return _payroll_guard(request) or render(request, 'web/payroll/report.html', {'page_title': 'Payroll Report'})


@web_login_required
@never_cache
def due_reminders_view(request):
    """Due Reminders — যাদের কাছে বাকি আছে তাদের তালিকা, আর WhatsApp / SMS এ রিমাইন্ডার পাঠানোর লিংক।"""
    if not has_perm(request.user, 'customers', 'view'):
        return forbidden(request, 'Due Reminders')
    return render(request, 'web/customers/due_reminders.html', {'page_title': 'Due Reminders'})


@web_login_required
@never_cache
def khata_view(request):
    """
    বাকি খাতা — TallyKhata / Khatabook ধরনের সহজ খাতা:
      • উপরে "মোট পাবো" (সবার বাকি একসাথে), আজ কত আদায় হলো
      • কাস্টমারের তালিকা — কার কাছে কত পাবো / কে অগ্রিম দিয়েছে
      • একজনকে খুললে: লেনদেনের খাতা (চলমান বাকি সহ), এক চাপে "টাকা পেলাম", "বাকিতে বিক্রি", WhatsApp/SMS তাগাদা

    নতুন কোনো হিসাব-নিয়ম নেই — সব কাজ পুরনো API দিয়েই:
      বাকির তালিকা   /api/reports/customer-due-reminders/   (Due Reminders পেজের একই হিসাব)
      খাতা           /api/reports/customer-ledger/           (Customer Ledger রিপোর্টের একই হিসাব)
      টাকা পেলাম     POST /api/money-receipts/               (Money Receipt এর একই পথ → Transaction → Account)
    তাই এখানে যা দেখায়, Customers / Reports / Money Receipt পেজেও ঠিক তাই দেখাবে।
    """
    u = request.user
    if not has_perm(u, 'customers', 'view'):
        return forbidden(request, 'Baki Khata')
    company = getattr(u, 'company', None)
    init = {
        'me': {'id': u.id, 'name': u.get_full_name() or u.username},
        'shop': {'name': getattr(company, 'name', '') or '', 'phone': getattr(company, 'phone', '') or ''},
        'perms': {
            'collect': has_perm(u, 'money_receipt', 'create'),
            'receipts': has_perm(u, 'money_receipt', 'view'),
            'sell': has_perm(u, 'sales', 'create'),
            'create': has_perm(u, 'customers', 'create'),
            'ledger': has_perm(u, 'reports', 'view'),
            'sales': has_perm(u, 'sales', 'view'),
            'due_create': has_perm(u, 'customers', 'create'),
            'due_delete': has_perm(u, 'customers', 'delete'),
        },
        'urls': {
            'sale': reverse('web:sale_new'),
            'receipts': reverse('web:receipts'),
            'customers': reverse('web:customers'),
        },
        'open': request.GET.get('c') or None,
    }
    return render(request, 'web/customers/khata.html', {'page_title': 'Baki Khata', 'khata_init': init})


@web_login_required
@never_cache
def warranty_view(request):
    """
    Warranty Check — কাস্টমার পণ্য নিয়ে এলে ইনভয়েস নং / ফোন / পণ্যের নাম দিয়ে খুঁজে দেখা ওয়ারেন্টি আছে কিনা,
    কবে শেষ। API: /api/reports/warranty/ (reports/warranty_views.py)
    """
    if not has_perm(request.user, 'sales', 'view'):
        return forbidden(request, 'Warranty Check')
    return render(request, 'web/sales/warranty.html', {'page_title': 'Warranty Check'})


REPORT_TITLES = {
    'sales': 'Sales Report', 'purchases': 'Purchase Report', 'profit-loss': 'Profit / Loss',
    'top-products': 'Top Selling Products', 'low-stock': 'Low Stock', 'stock': 'Stock Report',
    'customer-ledger': 'Customer Ledger', 'customer-due': 'Customer Due / Advance',
    'supplier-ledger': 'Supplier Ledger', 'supplier-due': 'Supplier Due / Advance', 'expenses': 'Expense Report',
}


# ---------------------------------------------------------------------------
# নতুন কোম্পানি নিবন্ধন (পাবলিক) — ১ মাস ফ্রি ট্রায়াল, নিবন্ধনকারী হয় ADMIN (Super Admin নয়)
# ---------------------------------------------------------------------------
TRIAL_DAYS = 30
REGISTER_LIMIT_PER_HOUR = 5   # একই IP থেকে ঘণ্টায় সর্বোচ্চ নিবন্ধন চেষ্টা (spam ঠেকাতে)


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or 'unknown'


@sensitive_post_parameters('password', 'password2')
@csrf_protect
@never_cache
def register_view(request):
    from core.models import Company
    from core.platform_views import _create_admin, _seed, _validate_admin, _validate_company

    if request.user.is_authenticated:
        return redirect('web:home')

    ctx = {'trial_days': TRIAL_DAYS, 'values': {}, 'errors': {}, 'error': None}
    if request.method != 'POST':
        return render(request, 'web/auth/register.html', ctx)

    post = request.POST
    ctx['values'] = {k: (post.get(k) or '').strip() for k in
                     ('company_name', 'phone', 'address', 'first_name', 'last_name', 'username', 'email')}

    # spam: লুকানো ঘর ভরা থাকলে (bot)। ঘরের নাম এমন রাখা যাতে browser এর autofill ভরে না দেয়,
    # আর ভরা থাকলেও চুপচাপ ফেরত না দিয়ে পরিষ্কার জানাই — নইলে আসল মানুষ বুঝতেই পারে না কী হলো।
    if post.get('hp_ref'):
        ctx['error'] = 'Could not complete the sign-up. Please reload the page and try again.'
        return render(request, 'web/auth/register.html', ctx, status=400)

    key = f'web-register:{_client_ip(request)}'
    attempts = cache.get(key, 0)
    if attempts >= REGISTER_LIMIT_PER_HOUR:
        ctx['error'] = 'Too many sign-up attempts from this connection. Please try again in an hour.'
        return render(request, 'web/auth/register.html', ctx, status=429)
    cache.set(key, attempts + 1, 60 * 60)

    v = ctx['values']
    cdata, cerr = _validate_company({
        'name': v['company_name'], 'phone': v['phone'], 'address': v['address'], 'email': v['email'],
    })
    adata, aerr = _validate_admin({
        'first_name': v['first_name'], 'last_name': v['last_name'], 'username': v['username'],
        'email': v['email'], 'phone': v['phone'], 'password': post.get('password') or '',
    })
    if (post.get('password') or '') != (post.get('password2') or ''):
        aerr['password2'] = 'The two passwords do not match.'
    if cerr or aerr:
        ctx['errors'] = {**{f'company_{k}': m for k, m in cerr.items()}, **aerr}
        ctx['errors']['company_name'] = cerr.get('name') or ctx['errors'].get('company_name')
        ctx['error'] = 'Please fix the highlighted fields.'
        return render(request, 'web/auth/register.html', ctx, status=400)

    # ট্রায়াল: আজ থেকে ৩০ দিন; plan basic; নিবন্ধনকারী ADMIN
    cdata['plan_type'] = 'basic'
    cdata['expiry_date'] = date.today() + timedelta(days=TRIAL_DAYS)
    cdata['is_active'] = True
    with transaction.atomic():
        company = Company(**cdata)
        from core.packages import start_trial
        start_trial(company)              # ফ্রি ট্রায়াল প্যাকেজ (সব মডিউল, অল্প সীমা) + মেয়াদ
        company.save()
        admin = _create_admin(company, adata, None)
        _seed(company, admin)

    login(request, admin, backend='django.contrib.auth.backends.ModelBackend')
    request.session.set_expiry(REMEMBER_SECONDS)
    request.session['web_client'] = 'web'
    messages.success(request, f'Welcome! {company.name} is ready — your {TRIAL_DAYS}-day free trial has started.')
    return redirect('web:home')


# ---------------------------------------------------------------------------
# Super Admin: একটা কোম্পানির ভেতরে ঢুকে সব দেখা (শুধু দেখা — সেভ/এডিট বন্ধ)
# ---------------------------------------------------------------------------
@require_POST
@csrf_protect
@web_login_required
def view_company_view(request, company_id):
    from core.middleware import PLATFORM_VIEW_SESSION_KEY
    from core.models import Company
    if not is_platform_admin(request.user) or getattr(request.user, 'company_id', None) and not request.platform_viewing:
        return forbidden(request, 'Companies')
    company = get_object_or_404(Company, pk=company_id)
    request.session[PLATFORM_VIEW_SESSION_KEY] = company.pk
    messages.info(request, f'Viewing {company.name} — view-only.')
    return redirect('web:home')


@require_POST
@csrf_protect
@web_login_required
def exit_company_view(request):
    from core.middleware import PLATFORM_VIEW_SESSION_KEY
    request.session.pop(PLATFORM_VIEW_SESSION_KEY, None)
    return redirect('web:platform_companies')


@web_login_required
@never_cache
def package_view(request):
    """
    আমার প্যাকেজ — দোকানের মালিক নিজে দেখেন: কোন প্যাকেজ, কবে শেষ, কতটা ব্যবহার হলো (সীমার বার),
    কোন মডিউল আছে / নেই, আর অন্য প্যাকেজের তুলনা + WhatsApp এ আপগ্রেডের অনুরোধ।
    টাকা নেওয়া হয় হাতে (bKash/নগদ) — Super Admin তারপর Companies পেজ থেকে মেয়াদ/প্যাকেজ বদলান।
    """
    from urllib.parse import quote
    from core.models import Package, PlatformSetting
    from core.packages import FEATURES, LIMITS, plan_for, usage

    company = getattr(request.user, 'company', None)
    if company is None:
        return redirect('web:home')
    plan = plan_for(company)
    ps = PlatformSetting.get()
    used = usage(company)
    from .templatetags.web_tags import current_lang
    bn = current_lang(request) == 'bn'
    limits = []
    for k, (en, b) in LIMITS.items():
        if k == 'max_branches':
            continue
        lim = plan.limit(k)
        u = used.get(k, 0)
        limits.append({'key': k, 'label': b if bn else en, 'used': u, 'max': lim,
                       'pct': min(100, round(u * 100 / lim)) if lim else 0,
                       'near': bool(lim) and u >= lim * 0.8, 'full': bool(lim) and u >= lim})
    features = [{'key': k, 'label': (v[1] if bn else v[0]), 'on': plan.has(k)} for k, v in FEATURES.items()]
    wa = ''.join(ch for ch in (ps.sales_whatsapp or '') if ch.isdigit())
    if wa.startswith('0'):
        wa = '88' + wa

    def wa_link(pkg_name=None, term=''):
        if not wa:
            return ''
        text = f'আসসালামু আলাইকুম। আমার দোকান: {company.name}। ' + (
            f'আমি "{pkg_name}" প্যাকেজ{term} নিতে চাই।' if pkg_name else 'আমি প্যাকেজ নবায়ন করতে চাই।')
        return f'https://wa.me/{wa}?text={quote(text)}'

    packages = []
    for p in Package.objects.filter(is_active=True, is_public=True).order_by('sort', 'id'):
        fs = set(p.features or [])
        name = (p.name_bn or p.name) if bn else p.name
        packages.append({
            'code': p.code, 'name': name, 'desc': p.description,
            'price_month': p.price_month, 'price_year': p.price_year, 'is_trial': p.is_trial, 'trial_days': p.trial_days,
            'current': plan.package is not None and plan.package.pk == p.pk,
            # বিক্রির সীমা: মোট-এ সীমা থাকলে (যেমন ট্রায়াল) সেটাই দেখাই, নইলে মাসিক
            'limits': [((LIMITS[k][1] if bn else LIMITS[k][0]), getattr(p, k))
                       for k in ('max_users', 'max_products', 'max_customers',
                                 'max_sales_total' if p.max_sales_total else 'max_sales_month', 'max_branches')],
            'features': [(v[1] if bn else v[0]) for k, v in FEATURES.items() if k in fs and not v[2]],
            'wa': '' if p.is_trial else wa_link(name, ' (মাসিক)'),
            'wa_year': '' if p.is_trial else wa_link(name, ' (বাৎসরিক)'),
        })
        # বাৎসরিক অফার: পাশে "মাসিক দামে ১২ মাস" কেটে দেখাই — আসল তুলনা, বানানো দাম নয়
        pm, py = float(p.price_month or 0), float(p.price_year or 0)
        full = pm * 12
        if pm and py and py < full:
            packages[-1].update({'year_full': full, 'year_save': full - py,
                                 'year_pct': round((full - py) * 100 / full),
                                 'months_free': round((full - py) / pm),
                                 'year_per_month': round(py / 12)})
    # কার্ডে লম্বা তালিকা না দিয়ে: ট্রায়াল → "সব মডিউল"; বাকিগুলো → "<আগের প্যাকেজ> এর সব, সাথে:" + শুধু নতুনগুলো
    n_extra = sum(1 for v in FEATURES.values() if not v[2])
    prev_full = None
    for p in packages:
        full = list(p['features'])
        p['all'] = len(full) >= n_extra
        p['plus_of'] = None
        if not p['is_trial']:
            if prev_full is not None:
                p['plus_of'] = prev_full[0]
                p['features'] = [f for f in full if f not in prev_full[1]]
            prev_full = (p['name'], full)
    locked = request.GET.get('f')
    pkg_name = ''
    if plan.package is not None:
        pkg_name = (plan.package.name_bn or plan.package.name) if bn else plan.package.name
    return render(request, 'web/package.html', {
        'page_title': 'My package',
        'plan': plan, 'pkg_name': pkg_name,
        'limits': limits, 'features': features, 'packages': packages,
        'renew_wa': wa_link(), 'sales_phone': ps.sales_phone, 'payment_note': ps.payment_note,
        'locked_label': (FEATURES[locked][1] if bn else FEATURES[locked][0]) if locked in FEATURES else '',
        'grace_days': ps.grace_days,
    })


@web_login_required
@never_cache
def branches_view(request):
    """
    শাখা — একাধিক দোকান/জায়গা থাকলে। ১টা শাখা থাকলে সফটওয়্যারের কোথাও শাখা দেখায় না; এখান থেকে
    দ্বিতীয় শাখা যোগ করলে তবেই ওপরে শাখা বাছাই, স্টাফকে শাখায় বসানো আর রিপোর্টে শাখা আসে।
    API: /api/branches/ (branch_warehouse/views.py) · নিয়ম: core/branches.py · সীমা: প্যাকেজের max_branches
    """
    user = request.user
    if not (user.is_superuser or getattr(user, 'role', '') in ('ADMIN', 'SUPER_ADMIN')) or not getattr(user, 'company', None):
        return forbidden(request, 'Branches')
    from core.packages import plan_for
    plan = plan_for(user.company)
    return render(request, 'web/admin/branches.html', {
        'page_title': 'Branches',
        'br_init': {'limit': 0 if plan.legacy else plan.limit('max_branches'),
                    'package_url': reverse('web:package'), 'staff_url': reverse('web:staff')},
    })


@web_login_required
@never_cache
def stock_transfers_view(request):
    """
    শাখায় মাল পাঠানো — এক শাখা থেকে কমে আরেক শাখায় যোগ, মোট স্টক একই থাকে।
    API: /api/branches/transfers/, /api/branches/stock/ (branch_warehouse/views.py)
    শুধু ২+ শাখা চালু থাকলে (অন্যদের মেনুতেই আসে না)।
    """
    user = request.user
    company = getattr(user, 'company', None)
    if company is None or not (has_perm(user, 'products', 'edit') or getattr(user, 'role', '') in ('ADMIN', 'SUPER_ADMIN')):
        return forbidden(request, 'Send stock')
    from core.branches import active_count
    if active_count(company) < 2:
        return redirect('web:branches')
    return render(request, 'web/admin/stock_transfers.html', {
        'page_title': 'Send stock',
        'st_init': {'own_branch': getattr(user, 'branch_id', None), 'current': getattr(request, 'dk_branch', {}) and request.dk_branch.get('id')},
    })
