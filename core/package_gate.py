"""
প্যাকেজের পাহারাদার (middleware) — web, mobile আর desktop অ্যাপ, সবার প্রতিটা অনুরোধ এখান দিয়ে যায়।

কী আটকায় (core/packages.py এর plan_for অনুযায়ী):
  1. মেয়াদ + grace শেষ ("শুধু দেখা"): GET চলে, নতুন কিছু লেখা (POST/PUT/PATCH/DELETE) আটকায়
  2. মডিউল প্যাকেজে নেই: সেই মডিউলের API/পেজ আটকায় (কিছু মডিউলের শুধু লেখা আটকায় — যেমন একাউন্ট,
     কারণ বিক্রির ফর্মেও একাউন্টের তালিকা লাগে)
  3. সীমা শেষ: নতুন পণ্য / কাস্টমার / বিক্রি / ইউজার যোগ আটকায় (পুরনো দেখা, টাকা নেওয়া, বাকি আদায় কখনো না)

কী কখনো আটকায় না: লগইন/লগআউট, প্রোফাইল, পাসওয়ার্ড, Super Admin, পুরনো (প্যাকেজ ছাড়া) কোম্পানি,
ডেস্কটপ offline sync (চলমান অ্যাপ হঠাৎ থেমে না যায়)।

উত্তর: API → 403 JSON {status:false, message, code: package_readonly | package_feature | package_limit, ...}
        web পেজ → "এই মডিউল আপনার প্যাকেজে নেই" পেজ, সাথে "আমার প্যাকেজ" এর লিংক
"""
import logging

from django.http import JsonResponse
from django.shortcuts import render

from .packages import FEATURES, LIMITS, limit_reached, plan_for

logger = logging.getLogger(__name__)
WRITE = ('POST', 'PUT', 'PATCH', 'DELETE')

# API: (/api/ এর পরের অংশের শুরু, feature, 'all' | 'write') — ওপর থেকে প্রথম মিলটাই ধরা হয়; feature None = সবসময় খোলা
API_RULES = [
    ('package/', None, 'all'), ('auth/', None, 'all'), ('api/token/', None, 'all'), ('token/', None, 'all'), ('profile/', None, 'all'),
    ('platform/', None, 'all'), ('dashboard/', None, 'all'), ('sync/audit', 'audit', 'all'), ('sync/', None, 'all'),
    ('user-permissions/update', 'staff', 'all'), ('user-permissions/reset', 'staff', 'all'), ('user-permissions', None, 'all'),
    # রিপোর্টের যেগুলো মূল পেজেই লাগে (ড্যাশবোর্ড, বাকি খাতা)
    ('reports/dashboard', None, 'all'), ('reports/low-stock-alert', None, 'all'),
    ('reports/customer-due-reminders', None, 'all'), ('reports/customer-ledger', None, 'all'),
    ('reports/export/', 'report_export', 'all'),
    ('reports/sales-returns', 'returns', 'all'), ('reports/purchase-returns', 'returns', 'all'), ('reports/bad-stock', 'returns', 'all'),
    ('reports/expiry-alerts', 'stock_tools', 'all'), ('reports/warranty', 'warranty', 'all'),
    ('reports/purchases', 'purchases', 'all'), ('reports/supplier', 'purchases', 'all'),
    ('reports/expenses', 'money', 'all'),
    ('reports/', 'reports', 'all'),
    ('sales-returns', 'returns', 'all'), ('purchase-returns', 'returns', 'all'), ('bad-stocks', 'returns', 'all'),
    ('sale-modes', 'sale_modes', 'write'), ('product-sale-modes', 'sale_modes', 'write'), ('price-tiers', 'sale_modes', 'write'),
    ('stock/', 'stock_tools', 'all'), ('day-close', 'stock_tools', 'all'),
    ('messages/', 'whatsapp', 'all'),
    ('income/', 'income_transfer', 'all'), ('transfers', 'income_transfer', 'all'),
    ('staffs', 'staff', 'all'), ('staff-roles', 'staff', 'all'),
    ('payroll/', 'payroll', 'all'),
    ('shop/', 'online_shop', 'all'),
    ('suppliers', 'purchases', 'all'), ('supplier-payments', 'purchases', 'all'), ('purchase', 'purchases', 'all'),
    ('expenses/', 'money', 'all'), ('transactions', 'money', 'all'),
    ('money-receipts', 'money', 'write'), ('accounts', 'money', 'write'),
]

# নতুন যোগ করার API (POST) → কোন সীমা
LIMIT_RULES = {
    'products/': ['max_products'],
    'customers/': ['max_customers'],
    'sales/': ['max_sales_month', 'max_sales_total'],
    'users/': ['max_users'],
    'branches/': ['max_branches'],
}

# web পেজ (url name) → feature
WEB_RULES = {
    'sales_returns': 'returns', 'sales_return_new': 'returns', 'purchase_returns': 'returns',
    'purchase_return_new': 'returns', 'bad_stock': 'returns',
    'sale_modes': 'sale_modes', 'warranty': 'warranty', 'due_reminders': 'whatsapp',
    'incomes': 'income_transfer', 'income_heads': 'income_transfer', 'transfers': 'income_transfer', 'transfer_new': 'income_transfer',
    'staff': 'staff', 'user_permissions': 'staff',
    'payroll': 'payroll', 'payroll_advances': 'payroll', 'payroll_report': 'payroll',
    'audit_log': 'audit', 'shop_orders': 'online_shop', 'shop_settings': 'online_shop',
    'purchases': 'purchases', 'purchase_new': 'purchases', 'suppliers': 'purchases',
    'supplier_payments': 'purchases', 'supplier_pay': 'purchases',
    'expenses': 'money', 'expense_heads': 'money', 'expense_subheads': 'money', 'receipts': 'money',
    'receipt_new': 'money', 'accounts': 'money', 'transactions': 'money',
    'report_purchases': 'purchases', 'report_supplier_ledger': 'purchases', 'report_supplier_due': 'purchases',
    'report_expenses': 'money',
}
WEB_REPORT_PREFIX = 'report_'
WEB_ALWAYS = {'login', 'logout', 'register', 'home', 'package', 'soon', 'platform_companies', 'view_company', 'exit_company'}


def feature_for_api(rest, method):
    for prefix, feat, mode in API_RULES:
        if rest.startswith(prefix):
            if feat is None or (mode == 'write' and method not in WRITE):
                return None
            return feat
    return None


def feature_for_web(url_name):
    if url_name in WEB_RULES:
        return WEB_RULES[url_name]
    if url_name and url_name.startswith(WEB_REPORT_PREFIX):
        return 'reports'
    return None


def _lang(request):
    v = request.COOKIES.get('dk-lang')
    if v in ('bn', 'en'):
        return v
    if not request.META.get('HTTP_AUTHORIZATION', '').startswith('Bearer '):
        # web (session): ভাষা না বাছলে web এর ডিফল্ট ভাষা — পেজ যে ভাষায় দেখায় সেই ভাষায় বার্তা
        from django.conf import settings
        return getattr(settings, 'WEB_DEFAULT_LANG', 'bn')
    return 'bn' if 'bn' in (request.META.get('HTTP_ACCEPT_LANGUAGE') or '').lower()[:5] else 'en'


def _msg(request, en, bn):
    return bn if _lang(request) == 'bn' else en


class PackageGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    # ───────── কে, কোন কোম্পানি ─────────
    @staticmethod
    def _user(request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return user
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth.startswith('Bearer '):
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                res = JWTAuthentication().authenticate(request)
                if res:
                    return res[0]
            except Exception:  # noqa: BLE001 — ভুল/মেয়াদোত্তীর্ণ token: view নিজেই 401 দেবে
                return None
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        path = request.path
        is_api = path.startswith('/api/')
        match = getattr(request, 'resolver_match', None)
        if not is_api and (not match or 'web' not in (match.namespaces or [])):
            return None     # Django admin, অনলাইন শপের পাবলিক পেজ ইত্যাদি
        user = self._user(request)
        if user is None:
            return None
        if getattr(request, 'platform_viewing', None):
            return None     # Super Admin দেখছেন — CompanyMiddleware নিজেই শুধু-দেখা রাখে
        company = getattr(user, 'company', None)
        if company is None:
            return None     # Super Admin (কোম্পানি নেই)
        try:
            plan = plan_for(company)
        except Exception:   # noqa: BLE001 — প্যাকেজের হিসাবে সমস্যা হলে দোকান আটকে দেব না
            logger.exception('package plan failed')
            return None
        if plan.legacy:
            return None
        request.package_plan = plan
        method = request.method.upper()

        if is_api:
            rest = path[len('/api/'):]
            if rest.startswith(('auth/', 'api/token/', 'token/', 'profile/', 'platform/')):
                return None
            # ১) শুধু-দেখা
            if plan.readonly and method in WRITE and not rest.startswith('sync/'):
                return self._api_block(request, 'package_readonly', _msg(
                    request,
                    'Your package has ended. You can still see your data, but you cannot add or change anything until you renew.',
                    'আপনার প্যাকেজের মেয়াদ শেষ। পুরনো হিসাব দেখতে পারবেন, কিন্তু নবায়ন না করা পর্যন্ত নতুন কিছু লেখা বা বদলানো যাবে না।'))
            # ২) মডিউল
            feat = feature_for_api(rest, method)
            if feat and not plan.has(feat):
                en, bn = FEATURES[feat][0], FEATURES[feat][1]
                return self._api_block(request, 'package_feature', _msg(
                    request, f'"{en}" is not in your package. Upgrade to use it.',
                    f'"{bn}" আপনার প্যাকেজে নেই। ব্যবহার করতে প্যাকেজ আপগ্রেড করুন।'), feature=feat)
            # ৩) সীমা
            if method == 'POST' and rest in LIMIT_RULES:
                for key in LIMIT_RULES[rest]:
                    hit, lim, used = limit_reached(company, plan, key)
                    if hit:
                        en, bn = LIMITS[key]
                        return self._api_block(request, 'package_limit', _msg(
                            request, f'Your package allows {lim} — {en.lower()} limit reached ({used}/{lim}). Upgrade to add more.',
                            f'আপনার প্যাকেজে {bn} সর্বোচ্চ {lim}টি — সীমা শেষ ({used}/{lim})। আরও যোগ করতে প্যাকেজ আপগ্রেড করুন।'),
                            limit=key, max=lim, used=used)
            return None

        # ───── web পেজ ─────
        name = match.url_name
        if name in WEB_ALWAYS:
            return None
        feat = feature_for_web(name)
        if feat and not plan.has(feat):
            return render(request, 'web/package_locked.html', {
                'page_title': FEATURES[feat][0], 'locked_feature': feat,
                'feature_en': FEATURES[feat][0], 'feature_bn': FEATURES[feat][1],
            }, status=403)
        return None

    @staticmethod
    def _api_block(request, code, message, **extra):
        return JsonResponse({'status': False, 'success': False, 'message': message, 'code': code,
                             'data': {'code': code, **extra}}, status=403)
