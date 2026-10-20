"""
অ্যাপের জন্য "আমার প্যাকেজ" — GET /api/package/

web এর /package/ পেজ যা দেখায় (core/packages.py), অ্যাপ সেটাই JSON এ পায়:
প্যাকেজের নাম, অবস্থা (active / grace / readonly), কত দিন বাকি, কোন মডিউল আছে,
সীমা ও ব্যবহার, সতর্কবার্তার ধরন, আর নবায়নের WhatsApp / ফোন / টাকা দেওয়ার নিয়ম।
পুরনো (প্যাকেজ ছাড়া) কোম্পানি: legacy=true — অ্যাপ তখন প্যাকেজের কিছু দেখায় না।
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .packages import FEATURES, LIMITS, plan_for, usage
from .utils import custom_response


class MyPackageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if company is None:
            return custom_response(True, 'No company', {'legacy': True})
        plan = plan_for(company)
        if plan.legacy:
            return custom_response(True, 'Legacy company', {'legacy': True})
        from .models import PlatformSetting
        ps = PlatformSetting.get()
        used = usage(company)
        pkg = plan.package
        wa = ''.join(ch for ch in (ps.sales_whatsapp or '') if ch.isdigit())
        if wa.startswith('0'):
            wa = '88' + wa
        return custom_response(True, 'Package', {
            'legacy': False,
            'code': pkg.code, 'name': pkg.name, 'name_bn': pkg.name_bn or pkg.name,
            'is_trial': pkg.is_trial, 'custom': plan.custom,
            'price_month': float(plan.price or 0),
            'state': plan.state, 'warn': plan.warn, 'days_left': plan.days_left,
            'expiry': plan.expiry.isoformat() if plan.expiry else None,
            'grace_days': ps.grace_days,
            'features': [{'key': k, 'en': v[0], 'bn': v[1], 'on': plan.has(k)} for k, v in FEATURES.items()],
            'limits': [{'key': k, 'en': en, 'bn': bn, 'max': plan.limit(k), 'used': used.get(k, 0)}
                       for k, (en, bn) in LIMITS.items()],
            'sales_whatsapp': wa, 'sales_phone': ps.sales_phone, 'payment_note': ps.payment_note,
        })
