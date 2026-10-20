"""
শাখা (ধাপ ১) — এক জায়গা থেকে সব: কোন শাখা এখন বাছা, তালিকা/রিপোর্ট ছাঁকা, নতুন এন্ট্রিতে শাখা বসানো।

কেন এভাবে:
  • সাধারণ দোকানে (১টা শাখা) কিছুই বদলায় না — "চালু" শুধু তখন যখন ২+ শাখা চালু আছে।
  • শাখা ফাঁকা (NULL) এন্ট্রি = প্রধান শাখার। তাই পুরনো ডাটা বদলাতে হয় না।
  • স্টাফকে শাখায় বসালে (User.branch) তাঁর সব নতুন এন্ট্রি সেই শাখার, আর তিনি শুধু সেই শাখার হিসাব দেখেন।
  • মালিক/Admin ওপরের বাছাই থেকে শাখা বাছেন (web session এ থাকে); "সব শাখা" = কোনো ছাঁকা নেই।
    অ্যাপ (JWT) থেকে ?branch=<id> বা X-Branch header দিয়েও বাছা যায়।

কাজ হয় একটা middleware (BranchMiddleware) দিয়ে — প্রতিটা অনুরোধে বাছা শাখা ঠিক করে contextvar এ রাখে।
নতুন Sale / Purchase / Expense / MoneyReceipt save হওয়ার আগে (pre_save signal) সেখান থেকে শাখা বসে।
"""
import contextvars

from django.db.models import Q

SESSION_KEY = 'dk_branch'
_state = contextvars.ContextVar('dk_branch_state', default=None)

# যেসব এন্ট্রিতে শাখা থাকে (app_label.Model)
TAGGED = ('sales.Sale', 'purchases.Purchase', 'expenses.Expense', 'money_receipts.MoneyReceipt')


def _branch_model():
    from branch_warehouse.models import Branch
    return Branch


def ensure_main(company):
    """প্রধান শাখা না থাকলে বানায় (দোকানের নামে) — প্রথম নতুন শাখা খোলার সময় ডাকা হয়"""
    Branch = _branch_model()
    main = Branch.objects.filter(company=company, is_main=True).first()
    if main is None:
        name = 'Main branch'
        if Branch.objects.filter(company=company, name=name).exists():
            name = 'Main branch (old shop)'
        main = Branch.objects.create(company=company, name=name, is_main=True)
        # শাখা-স্টক শুরু: এখনকার সব স্টক প্রধান শাখায় (branch_warehouse/stock.py)
        from branch_warehouse.stock import init_company
        init_company(company, main)
    return main


def active_count(company):
    if company is None:
        return 0
    return _branch_model().objects.filter(company=company, is_active=True).count()


def resolve(request, user):
    """এই অনুরোধে কোন শাখা — {'on': bool, 'id': int|None, 'main_id', 'locked', 'list': [...]}"""
    company = getattr(user, 'company', None) if user is not None else None
    if company is None:
        return {'on': False, 'id': None}
    Branch = _branch_model()
    rows = list(Branch.objects.filter(company=company, is_active=True).values('id', 'name', 'is_main'))
    if len(rows) < 2:
        return {'on': False, 'id': None}
    ids = {r['id'] for r in rows}
    main_id = next((r['id'] for r in rows if r['is_main']), None)
    st = {'on': True, 'id': None, 'main_id': main_id, 'locked': False, 'list': rows}
    own = getattr(user, 'branch_id', None)
    if own and own in ids:
        st.update(id=own, locked=True)
        return st
    raw = request.GET.get('branch') or request.META.get('HTTP_X_BRANCH')
    if raw is None and hasattr(request, 'session'):
        raw = request.session.get(SESSION_KEY)
    try:
        bid = int(raw) if raw not in (None, '', 'all') else None
    except (TypeError, ValueError):
        bid = None
    st['id'] = bid if bid in ids else None
    return st


def branch_state(request=None):
    """middleware যা ঠিক করেছে; না থাকলে খালি"""
    st = getattr(request, 'dk_branch', None) if request is not None else None
    return st or _state.get() or {'on': False, 'id': None}


def branch_q(field='branch', request=None):
    """তালিকা/রিপোর্ট ছাঁকার Q — শাখা বাছা না থাকলে Q() (সব)"""
    st = branch_state(request)
    bid = st.get('id')
    if not st.get('on') or not bid:
        return Q()
    q = Q(**{f'{field}_id': bid})
    if bid == st.get('main_id'):
        q |= Q(**{f'{field}__isnull': True})
    return q


def filter_qs(qs, field='branch', request=None):
    q = branch_q(field, request)
    return qs.filter(q) if q else qs


class BranchMiddleware:
    """PackageGateMiddleware এর পরে বসে (core/apps.py)"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _state.set(None)
        try:
            return self.get_response(request)
        finally:
            _state.reset(token)

    def process_view(self, request, view_func, view_args, view_kwargs):
        from core.package_gate import PackageGateMiddleware
        try:
            user = PackageGateMiddleware._user(request)
            if user is None:
                return None
            st = resolve(request, user)
        except Exception:  # noqa: BLE001 — শাখার হিসাবে সমস্যা হলে কাজ আটকাবো না
            return None
        request.dk_branch = st
        _state.set(st)
        return None


def tag_new_entry(sender, instance, **kwargs):
    """pre_save: নতুন এন্ট্রিতে শাখা বসানো (আগে থেকে বসানো থাকলে হাত দেয় না)"""
    if instance.pk is not None or getattr(instance, 'branch_id', None):
        return
    # মানি রিসিট বিক্রি থেকে এলে বিক্রির শাখাই
    sale = getattr(instance, 'sale', None) if hasattr(instance, 'sale_id') and instance.sale_id else None
    if sale is not None and getattr(sale, 'branch_id', None):
        instance.branch_id = sale.branch_id
        return
    st = _state.get()
    if st and st.get('on') and st.get('id'):
        instance.branch_id = st['id']
        return
    # অনুরোধের বাইরে (যেমন sync/কমান্ড): যিনি বানালেন তাঁর শাখা
    user = getattr(instance, 'created_by', None) if getattr(instance, 'created_by_id', None) else None
    if user is not None and getattr(user, 'branch_id', None):
        instance.branch_id = user.branch_id


def connect_signals():
    from django.apps import apps
    from django.db.models.signals import pre_save
    for label in TAGGED:
        model = apps.get_model(label)
        pre_save.connect(tag_new_entry, sender=model, dispatch_uid=f'dk_branch_tag_{label}')
