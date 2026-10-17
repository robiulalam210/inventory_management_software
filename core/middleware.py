PLATFORM_VIEW_SESSION_KEY = 'platform_view_company_id'
_SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def _is_platform_admin(user):
    return bool(user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN')


class CompanyMiddleware:
    """
    request.company সেট করে।

    Super Admin এর নিজের কোম্পানি নেই। সে Companies পেজ থেকে একটা কোম্পানি বেছে নিলে (session এ রাখা হয়)
    সেই কোম্পানির সব ডেটা দেখতে পারে — ওই কোম্পানির Admin যা দেখে হুবহু তাই। এই অবস্থায়:
      - শুধু দেখা যায় (GET); সেভ/এডিট/ডিলিট আটকানো হয়, যাতে ভুলে কোম্পানির ডেটা বদলে না যায়।
      - user.company শুধু memory তে বদলানো হয়, database এ কখনো লেখা হয় না।
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        request.platform_viewing = None
        if user and user.is_authenticated:
            request.company = getattr(user, "company", None)
            if request.company is None and _is_platform_admin(user):
                cid = request.session.get(PLATFORM_VIEW_SESSION_KEY)
                if cid:
                    from core.models import Company
                    company = Company.objects.filter(pk=cid).first()
                    if company is None:
                        request.session.pop(PLATFORM_VIEW_SESSION_KEY, None)
                    else:
                        if request.method not in _SAFE_METHODS and not self._allowed_write(request):
                            return self._read_only_response(request, company)
                        user.company = company          # memory তে; save() করা হয় না
                        request.company = company
                        request.platform_viewing = company
        else:
            request.company = None
        return self.get_response(request)

    @staticmethod
    def _allowed_write(request):
        """দেখার মধ্যেও যে POST গুলো চলবে: কোম্পানি বদলানো, বের হওয়া, sign out"""
        from django.urls import reverse
        allowed = {reverse('web:logout'), reverse('web:exit_company')}
        return request.path in allowed or request.path.rstrip('/').endswith('/enter')

    @staticmethod
    def _read_only_response(request, company):
        from django.http import HttpResponse, JsonResponse
        msg = (f"You are viewing {company.name} as Super Admin. This is view-only — "
               "exit the company to make changes elsewhere.")
        if request.path.startswith('/api/'):
            return JsonResponse({'success': False, 'message': msg, 'data': None}, status=403)
        return HttpResponse(msg, status=403, content_type='text/plain; charset=utf-8')
