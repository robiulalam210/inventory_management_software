from rest_framework import status
from rest_framework.response import Response
from core.base_viewsets import BaseCompanyViewSet
from .models import Account
from .serializers import AccountSerializer

class AccountViewSet(BaseCompanyViewSet):
    """CRUD API for accounts with company-based filtering."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()  # BaseCompanyViewSet filters by company
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # Ensure ac_number is None if blank or empty string
        for item in data:
            if item.get('ac_number') in ('', None):
                item['ac_number'] = None

        result = {
            'success': True,
            'total': len(data),
            'data': data
        }
        return Response(result)

    def perform_create(self, serializer):
        instance = serializer.save()
        # If balance is not set, initialize from opening_balance
        if instance.balance is None or instance.balance == 0:
            instance.balance = instance.opening_balance
            instance.save()