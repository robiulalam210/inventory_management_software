from rest_framework import status, serializers
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
        company = self.request.user.company
        ac_type = serializer.validated_data.get('ac_type')
        number = serializer.validated_data.get('number')
        
        # Uniqueness check for the same company, type, and number
        if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
            raise serializers.ValidationError(
                {"detail": "An account with this type and number already exists ."}
            )

        instance = serializer.save(company=company)

        # Initialize balance if not set
        if instance.balance is None or instance.balance == 0:
            instance.balance = instance.opening_balance
            instance.save()
