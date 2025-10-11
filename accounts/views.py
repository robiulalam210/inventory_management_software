from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    """CRUD API for accounts. List endpoint returns the JSON shape you provided."""
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # convert Decimal to string for exact match with example
        for item in data:
            # serializer already returns Decimal as string thanks to DecimalField
            # ensure ac_number null -> null in JSON
            if item.get('ac_number') in ('', ''):
                item['ac_number'] = None

        result = {
            'success': True,
            'total': len(data),
            'data': data
        }
        return Response(result)

    # Optionally override create/update to keep balance consistent
    def perform_create(self, serializer):
        instance = serializer.save()
        # if balance empty set to opening_balance
        if not instance.balance:
            instance.balance = instance.opening_balance
            instance.save()
