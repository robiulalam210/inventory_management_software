"""মোবাইল/ডেস্কটপ অ্যাপ থেকে নতুন কোম্পানি রেজিস্ট্রেশন (পাবলিক) — ১ মাস ফ্রি ট্রায়াল, নিবন্ধনকারী হয় ADMIN।
জবাবের আকার লগইন API র মতোই, তাই অ্যাপ সরাসরি লগইন করা অবস্থায় ঢুকতে পারে।"""
from datetime import date, timedelta

from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

TRIAL_DAYS = 30
LIMIT_PER_HOUR = 5


def _ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or 'unknown'


def login_payload(user, message='Login successful'):
    """CustomLoginView এর হুবহু জবাব"""
    from .serializers import CompanySerializer, CustomTokenObtainPairSerializer
    refresh = CustomTokenObtainPairSerializer().get_token(user)
    company = getattr(user, 'company', None)
    return {
        'success': True,
        'message': message,
        'data': {
            'user': {
                'id': user.id, 'username': user.username, 'email': user.email,
                'first_name': user.first_name, 'last_name': user.last_name, 'full_name': user.full_name,
                'role': user.role, 'permission_source': user.permission_source,
                'is_staff': user.is_staff, 'is_superuser': user.is_superuser,
                'permissions': user.get_permissions(),
            },
            'company': CompanySerializer(company).data if company else None,
            'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)},
        },
    }


class RegisterCompanyAPIView(APIView):
    """POST /api/auth/register-company/
    { company_name, phone?, address?, first_name, last_name?, username, email?, password }"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from core.models import Company
        from core.platform_views import _create_admin, _seed, _validate_admin, _validate_company

        key = f'api-register:{_ip(request)}'
        n = cache.get(key, 0)
        if n >= LIMIT_PER_HOUR:
            return Response({'success': False, 'message': 'Too many sign-up attempts. Please try again in an hour.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        cache.set(key, n + 1, 60 * 60)

        d = request.data
        g = lambda k: (str(d.get(k) or '')).strip()
        cdata, cerr = _validate_company({'name': g('company_name'), 'phone': g('phone'),
                                         'address': g('address'), 'email': g('email')})
        adata, aerr = _validate_admin({'first_name': g('first_name'), 'last_name': g('last_name'),
                                       'username': g('username'), 'email': g('email'),
                                       'phone': g('phone'), 'password': str(d.get('password') or '')})
        if cerr or aerr:
            errors = {**{f'company_{k}': v for k, v in cerr.items()}, **aerr}
            first = next(iter(errors.values()))
            return Response({'success': False, 'message': str(first), 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        cdata.update({'plan_type': 'basic', 'is_active': True,
                      'expiry_date': date.today() + timedelta(days=TRIAL_DAYS)})
        with transaction.atomic():
            company = Company(**cdata)
            from core.packages import start_trial
            start_trial(company)          # ফ্রি ট্রায়াল প্যাকেজ (সব মডিউল, অল্প সীমা) + মেয়াদ
            company.save()
            admin = _create_admin(company, adata, None)
            _seed(company, admin)
        return Response(login_payload(admin, f'{company.name} is ready — {TRIAL_DAYS}-day free trial started'),
                        status=status.HTTP_201_CREATED)
