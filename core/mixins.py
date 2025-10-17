# core/mixins.py
from rest_framework.permissions import IsAuthenticated

class CompanyFilteredViewSetMixin:
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == "super_admin":
            return qs
        if hasattr(qs.model, "company"):
            return qs.filter(company=user.company)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(serializer.Meta.model, "company") and user.company:
            serializer.save(company=user.company)
        else:
            serializer.save()
