"""
Web software এর প্রতিটা page এ লাগে: menu, user এর নাম/ছবি, company, মেয়াদের সতর্কতা।
শুধু /app/ এর page এ কাজ করে — Django admin বা API তে কিছু যোগ করে না।
"""
from .guides import guide_for
from .menu import build_menu


def _initials(name):
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def web_shell(request):
    # শুধু web software এর page এ (namespace 'web') — mount যেখানেই হোক (/app/ বা /) কাজ করে
    match = getattr(request, 'resolver_match', None)
    if not match or 'web' not in (match.namespaces or []):
        return {}
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    company = getattr(user, 'company', None)
    display_name = (getattr(user, 'full_name', '') or '').strip() or user.username

    # মেয়াদ শেষ / শিগগির শেষ — app এর মতোই login আটকানো হয় না, শুধু জানানো হয়
    expiry = None
    if company is not None and getattr(company, 'expiry_date', None):
        try:
            days = company.days_until_expiry() if callable(company.days_until_expiry) else company.days_until_expiry
        except Exception:
            days = None
        if days is not None and days <= 7:
            expiry = {'days': days, 'expired': days < 0}

    # প্যাকেজ (core/packages.py) — পুরনো (প্যাকেজ ছাড়া) কোম্পানির জন্য None, তখন আগের মেয়াদের বার্তাই থাকে
    web_plan = None
    if company is not None and getattr(company, 'package_id', None) and not getattr(request, 'platform_viewing', None):
        try:
            from core.models import PlatformSetting
            from core.packages import plan_for
            plan = plan_for(company)
            if not plan.legacy:
                days = plan.days_left
                grace_left = None
                if plan.state == 'grace' and days is not None:
                    grace_left = max(0, PlatformSetting.get().grace_days + days + 1)
                web_plan = {'warn': plan.warn, 'days': days, 'state': plan.state, 'grace_left': grace_left,
                            'name': plan.package.name, 'readonly': plan.readonly}
        except Exception:  # noqa: BLE001
            web_plan = None

    # শাখা (core/branches.py) — ২+ শাখা চালু থাকলেই শুধু; নইলে None, আর কোথাও শাখা দেখায় না
    web_branch = None
    st = getattr(request, 'dk_branch', None)
    if st and st.get('on') and not getattr(request, 'platform_viewing', None):
        cur = next((b for b in st.get('list', []) if b['id'] == st.get('id')), None)
        web_branch = {'list': st.get('list', []), 'id': st.get('id'), 'locked': st.get('locked', False),
                      'name': cur['name'] if cur else None, 'is_main': bool(cur and cur['is_main'])}

    # Low stock সতর্কতা শুধু তাদের দেখায় যারা stock/dashboard সম্পর্কিত কিছু দেখার অনুমতি পান
    # (API ও একই চারটা অনুমতি মানে — reports/views.py LowStockAlertView)
    try:
        perms = user.get_permissions() if hasattr(user, 'get_permissions') else {}
    except Exception:
        perms = {}
    low_stock_enabled = bool(company is not None) and (bool(user.is_superuser) or any(
        (perms.get(m) or {}).get('view') for m in ('dashboard', 'products', 'purchases', 'reports')))

    picture = getattr(user, 'profile_picture', None)
    logo = getattr(company, 'logo', None) if company else None
    return {
        'web_menu': build_menu(user, request.path),
        'web_user': {
            'name': display_name,
            'initials': _initials(display_name),
            'role': user.get_role_display() if hasattr(user, 'get_role_display') else '',
            'email': user.email,
            'picture': picture.url if picture else None,
        },
        'web_company': {
            'name': company.name if company else ('Platform console' if (getattr(user, 'role', '') == 'SUPER_ADMIN' or user.is_superuser) else 'No company'),
            'logo': logo.url if logo else None,
        },
        'web_expiry': expiry,
        'web_plan': web_plan,
        'web_branch': web_branch,
        'web_viewing': ({'name': request.platform_viewing.name} if getattr(request, 'platform_viewing', None) else None),
        'web_low_stock': low_stock_enabled,
        # পেজের উপরের বাংলা "কীভাবে কাজ করবেন" গাইড (web/guides.py)
        'web_guide': guide_for(getattr(getattr(request, 'resolver_match', None), 'url_name', None)),
    }
