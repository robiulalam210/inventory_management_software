# core/base_viewsets.py
from rest_framework import viewsets

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Automatically filter by logged-in user's company"""
    def get_queryset(self):
        queryset = super().get_queryset()
        company = getattr(self.request.user, "company", None)
        if company:
            return queryset.filter(company=company)
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)
