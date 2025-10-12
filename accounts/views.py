from rest_framework import status
from rest_framework.response import Response
from core.base_viewsets import BaseCompanyViewSet  # ✅ BaseCompanyViewSet ইমপোর্ট
from .models import Account
from .serializers import AccountSerializer
# core/urls.py

class AccountViewSet(BaseCompanyViewSet):  # ✅ ModelViewSet এর জায়গায় BaseCompanyViewSet
    """CRUD API for accounts with company-based filtering."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()  # ✅ BaseCompanyViewSet এটি company অনুযায়ী ফিল্টার করবে
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        for item in data:
            if item.get('ac_number') in ('', ''):
                item['ac_number'] = None

        result = {
            'success': True,
            'total': len(data),
            'data': data
        }
        return Response(result)

    def perform_create(self, serializer):
        instance = serializer.save()
        if not instance.balance:
            instance.balance = instance.opening_balance
            instance.save()
