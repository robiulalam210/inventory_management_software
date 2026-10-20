"""
প্যাকেজ — কোন কোম্পানি কোন মডিউল পাবে, কত পর্যন্ত (সীমা), আর মেয়াদের অবস্থা।

সবকিছু এখান থেকেই ঠিক হয় — web menu, API আটকানো (core/package_gate.py), "আমার প্যাকেজ" পেজ।

নিয়ম:
  • company.package ফাঁকা = পুরনো কোম্পানি → সব খোলা, নতুন কোনো সীমা নেই (আগে থেকে চলা দোকান কিছু হারায় না)
  • কাস্টম: company.custom_features দিলে সেটাই মডিউলের তালিকা; company.custom_limits দিলে শুধু সেই সীমাগুলো বদলায়
  • সীমায় 0 = আনলিমিটেড
  • মেয়াদ: শেষ তারিখ পর্যন্ত চালু → তারপর grace (PlatformSetting.grace_days, ডিফল্ট ৩ দিন) এ সব চলে →
    তারপর "শুধু দেখা": পুরনো হিসাব দেখা যায়, নতুন কিছু লেখা যায় না। ডাটা কখনো মোছে না।
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

# ─────────────────────────────── মডিউলের তালিকা ───────────────────────────────
# key → (English, বাংলা, সবসময় খোলা?)
FEATURES = {
    'sales':           ('Sales & POS',                         'বিক্রি ও POS', True),
    'khata':           ('Baki Khata & customers',              'বাকি খাতা ও কাস্টমার', True),
    'products':        ('Products & stock',                    'পণ্য ও স্টক', True),
    'purchases':       ('Purchase & suppliers',                'ক্রয় ও সাপ্লায়ার', False),
    'money':           ('Expenses, money receipts & accounts', 'খরচ, মানি রিসিট ও একাউন্ট', False),
    'reports':         ('Reports (on screen)',                 'রিপোর্ট (পর্দায়)', False),
    'report_export':   ('Report Excel / PDF',                  'রিপোর্ট Excel / PDF', False),
    'returns':         ('Returns & bad stock',                 'ফেরত ও নষ্ট মাল', False),
    'sale_modes':      ('Sale modes & barcode labels',         'সেল মোড ও বারকোড লেবেল', False),
    'stock_tools':     ('Batch/expiry, stocktake, day close',  'ব্যাচ/মেয়াদ, Stocktake, Day Close', False),
    'warranty':        ('Warranty',                            'ওয়ারেন্টি', False),
    'whatsapp':        ('WhatsApp reminders & messages',       'WhatsApp তাগাদা ও মেসেজ', False),
    'income_transfer': ('Income & account transfers',          'আয় ও ট্রান্সফার', False),
    'staff':           ('Staff & permissions',                 'স্টাফ ও অনুমতি', False),
    'payroll':         ('Payroll',                             'বেতন (Payroll)', False),
    'audit':           ('Audit log',                           'Audit log', False),
    'desktop_offline': ('Desktop offline app',                 'ডেস্কটপ offline অ্যাপ', False),
    'online_shop':     ('Online shop',                         'অনলাইন শপ', False),
}
CORE_FEATURES = {k for k, v in FEATURES.items() if v[2]}
ALL_FEATURES = set(FEATURES)

LIMITS = {
    # key → (English, বাংলা)
    'max_users':       ('Users', 'ইউজার'),
    'max_products':    ('Products', 'পণ্য'),
    'max_customers':   ('Customers', 'কাস্টমার'),
    'max_sales_month': ('Sales this month', 'এই মাসের বিক্রি'),
    'max_sales_total': ('Sales in total', 'মোট বিক্রি'),
    'max_branches':    ('Branches', 'শাখা'),
}

STARTER = ['sales', 'khata', 'products', 'purchases', 'money', 'reports']
STANDARD = STARTER + ['report_export', 'returns', 'sale_modes', 'stock_tools', 'warranty', 'whatsapp', 'income_transfer']
BUSINESS = sorted(ALL_FEATURES)

# শুরুর ৪টা প্যাকেজ (migration এ একবার বসে; পরে Super Admin বদলান — কোড আর ছুঁতে হয় না)
DEFAULT_PACKAGES = [
    dict(code='trial', name='Free trial', name_bn='ফ্রি ট্রায়াল', sort=0, is_trial=True, trial_days=30,
         description='30 days, every module, small amounts', price_month=0, price_year=0,
         max_users=2, max_products=30, max_customers=30, max_sales_month=0, max_sales_total=100, max_branches=1,
         features=BUSINESS),
    dict(code='starter', name='Starter', name_bn='স্টার্টার', sort=1,
         description='The basics for one small shop', price_month=149, price_year=1490,
         max_users=1, max_products=200, max_customers=200, max_sales_month=1000, max_sales_total=0, max_branches=1,
         features=STARTER),
    dict(code='standard', name='Standard', name_bn='স্ট্যান্ডার্ড', sort=2,
         description='Most modules, for a busy shop', price_month=299, price_year=2990,
         max_users=3, max_products=1000, max_customers=1000, max_sales_month=0, max_sales_total=0, max_branches=1,
         features=STANDARD),
    dict(code='business', name='Business', name_bn='বিজনেস', sort=3,
         description='Everything, with staff and branches', price_month=599, price_year=5990,
         max_users=8, max_products=5000, max_customers=5000, max_sales_month=0, max_sales_total=0, max_branches=3,
         features=BUSINESS),
]


@dataclass
class PlanInfo:
    legacy: bool
    package: object = None
    features: set = field(default_factory=set)
    limits: dict = field(default_factory=dict)
    state: str = 'active'            # active | grace | readonly
    days_left: int = None            # মেয়াদ শেষ হতে কত দিন (ঋণাত্মক = পেরিয়েছে)
    expiry: object = None
    custom: bool = False
    price: object = None

    def has(self, feature):
        return self.legacy or feature in self.features

    def limit(self, key):
        return 0 if self.legacy else int(self.limits.get(key) or 0)

    @property
    def readonly(self):
        return self.state == 'readonly'

    @property
    def warn(self):
        """ওপরের বার্তার জন্য: trial / শিগগির শেষ / grace / শুধু-দেখা"""
        if self.legacy:
            return None
        from core.models import PlatformSetting
        ps = PlatformSetting.get()
        if self.state in ('grace', 'readonly'):
            return self.state
        if self.package is not None and self.package.is_trial:
            return 'trial'
        if self.days_left is not None and self.days_left <= ps.warn_days:
            return 'ending'
        return None


def plan_for(company):
    """একটা কোম্পানির আজকের প্যাকেজের অবস্থা"""
    if company is None:
        return PlanInfo(legacy=True, features=set(ALL_FEATURES))
    pkg = company.package if company.package_id else None
    if pkg is None:
        return PlanInfo(legacy=True, features=set(ALL_FEATURES))
    from core.models import PlatformSetting
    ps = PlatformSetting.get()
    feats = company.custom_features if company.custom_features is not None else (pkg.features or [])
    features = (set(feats) & ALL_FEATURES) | CORE_FEATURES
    limits = {k: getattr(pkg, k) for k in LIMITS}
    for k, v in (company.custom_limits or {}).items():
        if k in LIMITS:
            try:
                limits[k] = max(0, int(v))
            except (TypeError, ValueError):
                pass
    today = timezone.localdate()
    exp = company.expiry_date
    state, days = 'active', None
    if exp:
        days = (exp - today).days
        if today > exp + timedelta(days=ps.grace_days):
            state = 'readonly'
        elif today > exp:
            state = 'grace'
    return PlanInfo(legacy=False, package=pkg, features=features, limits=limits, state=state, days_left=days,
                    expiry=exp, custom=company.custom_features is not None or bool(company.custom_limits),
                    price=company.custom_price if company.custom_price is not None else pkg.price_month)


def usage(company, keys=None):
    """এখন পর্যন্ত কতটা ব্যবহার — সীমার পাশে দেখানো ও আটকানোর জন্য"""
    from core.models import User
    out = {}
    keys = keys or list(LIMITS)
    now = timezone.localtime()
    if 'max_users' in keys:
        out['max_users'] = User.objects.filter(company=company, is_active=True).count()
    if 'max_products' in keys:
        from products.models import Product
        out['max_products'] = Product.objects.filter(company=company).count()
    if 'max_customers' in keys:
        from customers.models import Customer
        out['max_customers'] = Customer.objects.filter(company=company).count()
    if 'max_sales_month' in keys or 'max_sales_total' in keys:
        from sales.models import Sale
        qs = Sale.objects.filter(company=company)
        if 'max_sales_month' in keys:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            out['max_sales_month'] = qs.filter(sale_date__gte=start).count()
        if 'max_sales_total' in keys:
            out['max_sales_total'] = qs.count()
    if 'max_branches' in keys:
        from branch_warehouse.models import Branch
        out['max_branches'] = max(1, Branch.objects.filter(company=company, is_active=True).count())  # শাখা না থাকলেও দোকান নিজেই ১টা
    return out


def limit_reached(company, plan, key):
    """(আটকাবে কিনা, সীমা, ব্যবহার)"""
    lim = plan.limit(key)
    if not lim:
        return False, 0, None
    used = usage(company, [key]).get(key, 0)
    return used >= lim, lim, used


def start_trial(company):
    """নতুন কোম্পানি: ট্রায়াল প্যাকেজ + মেয়াদ (save করে না)"""
    from core.models import Package
    pkg = Package.objects.filter(is_trial=True, is_active=True).order_by('sort').first()
    if pkg is not None:
        company.package = pkg
        company.expiry_date = timezone.localdate() + timedelta(days=pkg.trial_days or 30)
    return pkg
