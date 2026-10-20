"""মোবাইল/ডেস্কটপ অ্যাপের জন্য Super Admin এর "কোম্পানির ভেতরে দেখা" (View data)।

ওয়েবে এটা session দিয়ে চলে (core/middleware.py)। অ্যাপ JWT token ব্যবহার করে, তাই অ্যাপ প্রতিটা request এ
`X-View-Company: <company id>` header পাঠায়। Super Admin (যার নিজের কোম্পানি নেই) এই header দিলে সেই
কোম্পানির Admin যা দেখে হুবহু তাই দেখে — তবে শুধু দেখা (GET); সেভ/এডিট/ডিলিট আটকানো হয়।
user.company শুধু memory তে বদলায়, database এ কখনো লেখা হয় না।
"""
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def install():
    """JWT authentication এ header টা বুঝে নেওয়ার hook — core.apps.CoreConfig.ready() থেকে একবার ডাকা হয়।"""
    from rest_framework_simplejwt.authentication import JWTAuthentication

    if getattr(JWTAuthentication, '_view_as_installed', False):
        return
    original = JWTAuthentication.authenticate

    def authenticate(self, request):
        result = original(self, request)
        if result is None:
            return result
        company_id = request.META.get('HTTP_X_VIEW_COMPANY')
        if not company_id:
            return result
        user, token = result
        is_super = user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN'
        if not is_super or getattr(user, 'company_id', None):
            return result   # সাধারণ user এ header এর কোনো প্রভাব নেই

        from rest_framework.exceptions import PermissionDenied
        from core.models import Company

        if request.method not in SAFE_METHODS:
            raise PermissionDenied("You are viewing a company as Super Admin. This is view-only.")
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            raise PermissionDenied("Company not found")
        user.company = company          # memory তে; save() করা হয় না
        return user, token

    JWTAuthentication.authenticate = authenticate
    JWTAuthentication._view_as_installed = True
