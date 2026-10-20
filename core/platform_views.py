"""
Platform (Super Admin) — সব কোম্পানি দেখা, নতুন কোম্পানি খোলা, তার এডমিন বানানো, মেয়াদ/প্ল্যান ঠিক করা,
কোম্পানি বন্ধ/চালু করা, এডমিনের password বদলে দেওয়া।

শুধু SUPER_ADMIN (বা Django superuser) ব্যবহার করতে পারে। কোম্পানির নিজের admin এখানে ঢুকতে পারে না —
না হলে সে নিজের মেয়াদ বা user limit নিজেই বাড়িয়ে নিতে পারত।

  GET   /api/platform/companies/?q=&status=all|active|suspended|expiring|expired
  POST  /api/platform/companies/                     { company:{...}, admin:{...}, seed:true }
  GET   /api/platform/companies/<id>/                 কোম্পানি + তার user রা
  PATCH /api/platform/companies/<id>/                 { name, phone, …, plan_type, expiry_date, is_active, max_* }
  POST  /api/platform/companies/<id>/admins/          { first_name, last_name, username, email, phone, password }
  POST  /api/platform/companies/<id>/users/<uid>/password/   { password }
  POST  /api/platform/companies/<id>/users/<uid>/toggle/     চালু ↔ বন্ধ

কোম্পানি মুছে ফেলার কোনো পথ রাখা হয়নি — মুছলে CASCADE এ তার সব বিক্রি, কেনা, হিসাব মুছে যায়।
বন্ধ (suspend) করলেই তার কেউ আর login করতে পারে না।
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from .models import Company
from .utils import custom_response

User = get_user_model()

PLANS = [c[0] for c in Company.PlanType.choices]

# নতুন কোম্পানির প্রথম দিনের জন্য — unit ছাড়া product তৈরি হয় না, আর account ছাড়া বিক্রির টাকা কোথাও ওঠে না
DEFAULT_UNITS = [
    ('Pieces', 'pcs'), ('Kilogram', 'kg'), ('Gram', 'g'), ('Litre', 'L'),
    ('Box', 'box'), ('Packet', 'pkt'), ('Dozen', 'dz'),
]


class IsSuperAdmin(BasePermission):
    message = 'Only the platform super admin can do this.'

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (getattr(u, 'role', '') == User.Role.SUPER_ADMIN or u.is_superuser))


def _err(message, errors=None, code=status.HTTP_400_BAD_REQUEST):
    return custom_response(False, message, errors, code)


def _clean(v):
    return (v or '').strip() if isinstance(v, str) else v


def _user_row(u):
    return {
        'id': u.id, 'username': u.username, 'email': u.email or '', 'phone': u.phone or '',
        'name': (u.get_full_name() or '').strip() or u.username, 'first_name': u.first_name, 'last_name': u.last_name,
        'role': u.role, 'is_active': u.is_active,
        'last_login': u.last_login.isoformat() if u.last_login else None,
        'date_joined': u.date_joined.isoformat() if u.date_joined else None,
    }


def _eff_limit(c, key):
    from .packages import plan_for
    try:
        return plan_for(c).limit(key)
    except Exception:  # noqa: BLE001
        return getattr(c, key, 0)


def _company_row(c, admins=None):
    days = (c.expiry_date - date.today()).days if c.expiry_date else None
    if not c.is_active:
        state = 'suspended'
    elif days is not None and days < 0:
        state = 'expired'
    elif days is not None and days <= 30:
        state = 'expiring'
    else:
        state = 'active'
    row = {
        'id': c.id, 'name': c.name, 'company_code': c.company_code,
        'phone': c.phone or '', 'email': c.email or '', 'address': c.address or '',
        'trade_license': c.trade_license or '', 'website': c.website or '',
        'logo': c.logo.url if c.logo else None,
        'currency': c.currency, 'timezone': c.timezone,
        'plan_type': c.plan_type, 'start_date': c.start_date.isoformat() if c.start_date else None,
        'expiry_date': c.expiry_date.isoformat() if c.expiry_date else None, 'days_left': days,
        'is_active': c.is_active, 'state': state,
        'max_users': c.max_users, 'max_products': c.max_products, 'max_branches': c.max_branches,
        'user_count': getattr(c, 'n_users', None), 'active_user_count': getattr(c, 'n_active_users', None),
        'product_count': getattr(c, 'n_products', None),
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'package': c.package.code if c.package_id else None,
        'package_name': c.package.name if c.package_id else 'Legacy (no limits)',
        'custom_features': c.custom_features, 'custom_limits': c.custom_limits,
        'custom_price': float(c.custom_price) if c.custom_price is not None else None,
        'package_note': c.package_note,
        'package_state': _plan_state(c),
        # আসল ইউজার সীমা: প্যাকেজ থাকলে প্যাকেজ/কাস্টম থেকে (0 = আনলিমিটেড), না থাকলে পুরনো max_users
        'user_limit': (_eff_limit(c, 'max_users') if c.package_id else c.max_users),
        'product_limit': (_eff_limit(c, 'max_products') if c.package_id else c.max_products),
        'branch_limit': (_eff_limit(c, 'max_branches') if c.package_id else c.max_branches),
    }
    if admins is not None:
        row['admins'] = admins
    return row


def _activity(ids):
    """
    প্রতি কোম্পানি কেমন চলছে — মালিক (Super Admin) এর এক নজরের জন্য:
      last_activity  — শেষ কবে কেউ কিছু করেছে (Audit log এর শেষ entry)
      last_sale      — শেষ বিক্রি
      sales_7d_count / sales_7d_total — গত ৭ দিনের বিক্রি
      activity       — busy (গত ৩ দিনে কাজ) / quiet (৪–১৪ দিন) / idle (১৪ দিনের বেশি) / new (এখনো কোনো কাজ হয়নি)
    """
    from offline_sync.models import ChangeLog
    from sales.models import Sale

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    last_log = dict(ChangeLog.objects.filter(company_id__in=ids).values_list('company_id').annotate(m=Max('created_at')))
    last_sale = dict(Sale.objects.filter(company_id__in=ids).values_list('company_id').annotate(m=Max('sale_date')))
    wk = {r['company_id']: r for r in Sale.objects.filter(company_id__in=ids, sale_date__gte=week_ago)
          .values('company_id').annotate(n=Count('id'), t=Sum('grand_total'))}
    out = {}
    for cid in ids:
        cand = [d for d in (last_log.get(cid), last_sale.get(cid)) if d]
        last = max(cand) if cand else None
        if last is None:
            kind, idle_days = 'new', None
        else:
            idle_days = (now - last).days
            kind = 'busy' if idle_days <= 3 else 'quiet' if idle_days <= 14 else 'idle'
        w = wk.get(cid) or {}
        out[cid] = {
            'last_activity': last.isoformat() if last else None,
            'last_sale': last_sale[cid].isoformat() if last_sale.get(cid) else None,
            'idle_days': idle_days, 'activity': kind,
            'sales_7d_count': w.get('n', 0) or 0,
            'sales_7d_total': float(w.get('t') or 0),
        }
    return out


def _platform_summary(all_ids, act):
    """মালিকের এক নজরের সারাংশ — সব কোম্পানি মিলিয়ে (status/search ফিল্টারে বদলায় না)"""
    from sales.models import Sale

    now = timezone.now()
    today = timezone.localdate()
    week_ago = now - timedelta(days=7)
    working_today = idle = never = 0
    sales_7d_count = 0
    sales_7d_total = 0.0
    for cid in all_ids:
        a = act.get(cid) or {}
        sales_7d_count += a.get('sales_7d_count', 0)
        sales_7d_total += a.get('sales_7d_total', 0.0)
        if a.get('activity') == 'new':
            never += 1
        elif a.get('activity') == 'idle':
            idle += 1
        if a.get('last_activity') and a['last_activity'][:10] == str(today):
            working_today += 1
    t = Sale.objects.filter(company_id__in=all_ids, sale_date__date=today).exclude(payment_status='cancelled') \
        .aggregate(n=Count('id'), s=Sum('grand_total'))
    return {
        'companies': len(all_ids),
        'new_7d': Company.objects.filter(created_at__gte=week_ago).count(),
        'working_today': working_today,
        'idle': idle,
        'never_used': never,
        'sales_today_count': t['n'] or 0,
        'sales_today_total': float(t['s'] or 0),
        'sales_7d_count': sales_7d_count,
        'sales_7d_total': round(sales_7d_total, 2),
    }


def _annotated():
    return Company.objects.annotate(
        n_users=Count('users', distinct=True),
        n_active_users=Count('users', filter=Q(users__is_active=True), distinct=True),
        n_products=Count('products', distinct=True),
    )


def _validate_company(data, instance=None):
    """কোম্পানির ঘরগুলো যাচাই করে (cleaned, errors) ফেরত দেয়। PATCH এ শুধু পাঠানো ঘরগুলো দেখে।"""
    out, errors = {}, {}
    partial = instance is not None

    def has(k):
        return k in data or not partial

    if has('name'):
        name = _clean(data.get('name'))
        if not name:
            errors['name'] = 'Enter the company name.'
        elif len(name) > 150:
            errors['name'] = 'Keep the name under 150 characters.'
        elif Company.objects.filter(name__iexact=name).exclude(pk=getattr(instance, 'pk', None)).exists():
            errors['name'] = 'A company with this name already exists.'
        else:
            out['name'] = name
    for k, mx in (('phone', 20), ('trade_license', 100), ('address', 2000), ('currency', 10), ('timezone', 50)):
        if k in data:
            v = _clean(data.get(k))
            if v and len(v) > mx:
                errors[k] = f'Keep it under {mx} characters.'
            else:
                out[k] = v or (None if k not in ('currency', 'timezone') else ('BDT' if k == 'currency' else 'Asia/Dhaka'))
    if 'email' in data:
        v = _clean(data.get('email'))
        if v:
            try:
                validate_email(v)
                out['email'] = v
            except DjangoValidationError:
                errors['email'] = 'Enter a valid email address.'
        else:
            out['email'] = None
    if 'website' in data:
        v = _clean(data.get('website'))
        if v and not v.startswith(('http://', 'https://')):
            v = 'https://' + v
        out['website'] = v or None
    if 'plan_type' in data:
        if data.get('plan_type') not in PLANS:
            errors['plan_type'] = 'Pick a plan.'
        else:
            out['plan_type'] = data['plan_type']
    if 'expiry_date' in data:
        v = data.get('expiry_date')
        try:
            out['expiry_date'] = date.fromisoformat(v) if v else None
            if out['expiry_date'] is None:
                errors['expiry_date'] = 'Pick the date the subscription ends.'
        except (TypeError, ValueError):
            errors['expiry_date'] = 'Enter a valid date.'
    for k in ('max_users', 'max_products', 'max_branches'):
        if k in data:
            try:
                v = int(data.get(k))
                if v < 1 or v > 1000000:
                    raise ValueError
                out[k] = v
            except (TypeError, ValueError):
                errors[k] = 'Enter a whole number, 1 or more.'
    if 'is_active' in data:
        out['is_active'] = bool(data.get('is_active'))
    # ── প্যাকেজ (core/packages.py) ──
    from core.models import Package
    from core.packages import ALL_FEATURES, LIMITS
    if 'package' in data:
        v = data.get('package')
        if v in (None, '', 'legacy'):
            out['package'] = None
        else:
            pkg = Package.objects.filter(code=str(v)).first() or (Package.objects.filter(pk=v).first() if str(v).isdigit() else None)
            if pkg is None:
                errors['package'] = 'Pick a package.'
            else:
                out['package'] = pkg
    if 'custom_features' in data:
        v = data.get('custom_features')
        if v is None:
            out['custom_features'] = None
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            out['custom_features'] = sorted(set(v) & ALL_FEATURES)
        else:
            errors['custom_features'] = 'Pick the modules.'
    if 'custom_limits' in data:
        v = data.get('custom_limits') or {}
        if not isinstance(v, dict):
            errors['custom_limits'] = 'Invalid limits.'
        else:
            clean = {}
            for k, x in v.items():
                if k in LIMITS and x not in (None, ''):
                    try:
                        clean[k] = max(0, int(x))
                    except (TypeError, ValueError):
                        errors['custom_limits'] = f'{LIMITS[k][0]}: enter a whole number (0 = unlimited).'
            out['custom_limits'] = clean or None
    if 'custom_price' in data:
        v = data.get('custom_price')
        try:
            out['custom_price'] = None if v in (None, '') else round(float(v), 2)
        except (TypeError, ValueError):
            errors['custom_price'] = 'Enter a price.'
    if 'package_note' in data:
        out['package_note'] = (_clean(data.get('package_note')) or '')[:255]
    return out, errors


def _plan_state(c):
    from core.packages import plan_for
    p = plan_for(c)
    return 'legacy' if p.legacy else p.state


def _validate_admin(data, company=None):
    out, errors = {}, {}
    out['first_name'] = (_clean(data.get('first_name')) or '')[:150]
    out['last_name'] = (_clean(data.get('last_name')) or '')[:150]
    if not out['first_name']:
        errors['first_name'] = "Enter the admin's name."
    username = _clean(data.get('username'))
    if not username:
        errors['username'] = 'Choose a username to log in with.'
    elif len(username) < 3 or len(username) > 150 or not all(ch.isalnum() or ch in '._-' for ch in username):
        errors['username'] = 'Use 3+ letters, numbers, dot, dash or underscore — no spaces.'
    elif User.objects.filter(username__iexact=username).exists():
        errors['username'] = 'This username is taken.'
    else:
        out['username'] = username
    email = _clean(data.get('email'))
    if email:
        try:
            validate_email(email)
            # email দিয়েও login হয় — একই email দুজনের হলে login ভেঙে যায়
            if User.objects.filter(email__iexact=email).exists():
                errors['email'] = 'Another user already has this email.'
            else:
                out['email'] = email
        except DjangoValidationError:
            errors['email'] = 'Enter a valid email address.'
    else:
        out['email'] = ''
    out['phone'] = (_clean(data.get('phone')) or '')[:20] or None
    pw = data.get('password') or ''
    if not pw:
        errors['password'] = 'Set a password.'
    else:
        try:
            validate_password(pw, user=User(username=username or '', email=email or ''))
            out['password'] = pw
        except DjangoValidationError as e:
            errors['password'] = ' '.join(e.messages)
    return out, errors


def _create_admin(company, d, by):
    u = User(username=d['username'], email=d['email'], first_name=d['first_name'], last_name=d['last_name'],
             phone=d['phone'], company=company, role=User.Role.ADMIN, is_active=True)
    if hasattr(u, 'created_by'):
        u.created_by = by
    u.set_password(d['password'])
    u.save()
    return u


def _seed(company, admin):
    """প্রথম দিনেই কাজ শুরু করা যায় এমন default — একই নামের থাকলে বাদ দেয়"""
    from products.models import Unit
    from accounts.models import Account
    made = {'units': 0, 'accounts': 0}
    for name, code in DEFAULT_UNITS:
        if not Unit.objects.filter(company=company, name__iexact=name).exists():
            Unit.objects.create(company=company, name=name, code=code, created_by=admin)
            made['units'] += 1
    if not Account.objects.filter(company=company, ac_type=Account.TYPE_CASH).exists():
        Account.objects.create(company=company, name='Cash', ac_type=Account.TYPE_CASH,
                               opening_balance=Decimal('0.00'), created_by=admin)
        made['accounts'] += 1
    return made


class PlatformCompanyListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        qs = _annotated().order_by('-created_at')
        q = _clean(request.query_params.get('q'))
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(company_code__icontains=q) | Q(phone__icontains=q)
                           | Q(email__icontains=q) | Q(users__username__icontains=q)).distinct()
        rows = [_company_row(c) for c in qs]
        counts = {k: 0 for k in ('all', 'active', 'expiring', 'expired', 'suspended')}
        for r in rows:
            counts['all'] += 1
            counts[r['state']] += 1
        st = request.query_params.get('status') or 'all'
        if st != 'all':
            rows = [r for r in rows if r['state'] == st]
        # প্রতি কোম্পানির প্রথম admin — তালিকায় দেখানোর জন্য
        ids = [r['id'] for r in rows]
        first_admin = {}
        for u in User.objects.filter(company_id__in=ids, role=User.Role.ADMIN).order_by('date_joined'):
            first_admin.setdefault(u.company_id, {'username': u.username, 'name': (u.get_full_name() or '').strip() or u.username})
        for r in rows:
            r['admin'] = first_admin.get(r['id'])
        # একবারেই সব কোম্পানির কাজের হিসাব — তালিকা ও ওপরের সারাংশ দুটোতেই লাগে
        all_ids = list(Company.objects.values_list('id', flat=True))
        act = _activity(all_ids)
        for r in rows:
            r.update(act.get(r['id'], {}))
        return custom_response(True, f'{len(rows)} companies', {
            'results': rows, 'counts': counts, 'summary': _platform_summary(all_ids, act)})

    def post(self, request):
        body = request.data or {}
        cdata, cerr = _validate_company(body.get('company') or {})
        adata, aerr = _validate_admin(body.get('admin') or {})
        if cerr or aerr:
            return _err('Please fix the highlighted fields.', {'company': cerr, 'admin': aerr})
        with transaction.atomic():
            company = Company(**cdata)
            if 'package' not in cdata:
                from core.packages import start_trial
                start_trial(company)      # প্যাকেজ না বাছলে: ফ্রি ট্রায়াল + মেয়াদ
            if not company.expiry_date:
                company.expiry_date = date.today() + timedelta(days=365)
            company.save()
            admin = _create_admin(company, adata, request.user)
            seeded = _seed(company, admin) if body.get('seed', True) else {'units': 0, 'accounts': 0}
        company = _annotated().get(pk=company.pk)
        return custom_response(True, f'{company.name} is ready.', {
            'company': _company_row(company, [_user_row(admin)]),
            'admin': _user_row(admin), 'seeded': seeded,
        }, status.HTTP_201_CREATED)


class PlatformCompanyDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def _payload(self, pk):
        c = get_object_or_404(_annotated(), pk=pk)
        users = [_user_row(u) for u in User.objects.filter(company=c).order_by('-role', 'date_joined')]
        users.sort(key=lambda u: (u['role'] != User.Role.ADMIN, not u['is_active'], u['name'].lower()))
        return _company_row(c, users)

    def get(self, request, pk):
        return custom_response(True, 'Company', self._payload(pk))

    def patch(self, request, pk):
        c = get_object_or_404(Company, pk=pk)
        data, errors = _validate_company(request.data or {}, instance=c)
        if errors:
            return _err('Please fix the highlighted fields.', {'company': errors})
        for k, v in data.items():
            setattr(c, k, v)
        # মেয়াদ বাড়িয়ে চালু করলে Company.save() আবার বন্ধ করে না; মেয়াদ পার হয়ে থাকলে save() নিজেই বন্ধ করে
        c.save()
        msg = 'Saved.'
        if 'is_active' in data:
            msg = f'{c.name} is active again.' if c.is_active else f'{c.name} is suspended. Its users can no longer sign in.'
        if data.get('is_active') and not c.is_active:
            msg = 'The subscription has ended, so it stays suspended. Extend the end date first.'
        return custom_response(True, msg, self._payload(pk))


class PlatformCompanyAdminView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk):
        c = get_object_or_404(Company, pk=pk)
        d, errors = _validate_admin(request.data or {})
        if errors:
            return _err('Please fix the highlighted fields.', {'admin': errors})
        if c.users.filter(is_active=True).count() >= c.max_users:
            return _err(f'{c.name} already has {c.max_users} active users, the most its plan allows. Raise the user limit first.')
        with transaction.atomic():
            u = _create_admin(c, d, request.user)
        return custom_response(True, f'{u.username} can now sign in as admin of {c.name}.', _user_row(u), status.HTTP_201_CREATED)


class PlatformUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk, uid):
        u = get_object_or_404(User, pk=uid, company_id=pk)
        pw = (request.data or {}).get('password') or ''
        try:
            validate_password(pw, user=u)
        except DjangoValidationError as e:
            return _err(' '.join(e.messages), {'password': ' '.join(e.messages)})
        u.set_password(pw)
        u.save(update_fields=['password'])
        return custom_response(True, f'Password changed for {u.username}.', _user_row(u))


class PlatformUserToggleView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk, uid):
        u = get_object_or_404(User, pk=uid, company_id=pk)
        if u.pk == request.user.pk:
            return _err("You can't turn off your own account.")
        if not u.is_active and u.company.users.filter(is_active=True).count() >= u.company.max_users:
            return _err(f'{u.company.name} is at its limit of {u.company.max_users} active users.')
        u.is_active = not u.is_active
        u.save(update_fields=['is_active'])
        return custom_response(True, f'{u.username} can sign in again.' if u.is_active else f'{u.username} can no longer sign in.', _user_row(u))


class PlatformPackageListView(APIView):
    """GET /api/platform/packages/ — প্যাকেজ আর মডিউলের তালিকা (Super Admin এর কোম্পানি ফর্মের জন্য)"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from core.models import Package
        from core.packages import FEATURES, LIMITS
        rows = [{'code': p.code, 'name': p.name, 'name_bn': p.name_bn, 'price_month': float(p.price_month),
                 'price_year': float(p.price_year), 'is_trial': p.is_trial, 'trial_days': p.trial_days,
                 'features': p.features, **{k: getattr(p, k) for k in LIMITS}, 'is_active': p.is_active}
                for p in Package.objects.all()]
        feats = [{'key': k, 'label': v[0], 'label_bn': v[1], 'core': v[2]} for k, v in FEATURES.items()]
        lims = [{'key': k, 'label': v[0], 'label_bn': v[1]} for k, v in LIMITS.items()]
        return custom_response(True, f'{len(rows)} packages', {'packages': rows, 'features': feats, 'limits': lims})
