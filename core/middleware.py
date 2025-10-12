class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            # Lazy import to avoid AppRegistryNotReady
            from core.models import Company
            request.company = getattr(user, "company", None)
        else:
            request.company = None
        return self.get_response(request)
