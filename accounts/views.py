from rest_framework import status, serializers
from core.base_viewsets import BaseCompanyViewSet
from .models import Account
from .serializers import AccountSerializer
from core.utils import custom_response

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

        return custom_response(
            success=True,
            message="Account list fetched successfully.",
            data=data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = self.request.user.company
            ac_type = serializer.validated_data.get('ac_type')
            number = serializer.validated_data.get('ac_number')  # <-- Use 'number' here

            # Uniqueness check for the same company, type, and number
            if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
                return custom_response(
                    success=False,
                    message="An account with this type and number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            instance = serializer.save(company=company)

            # Initialize balance if not set
            if instance.balance is None or instance.balance == 0:
                instance.balance = instance.opening_balance
                instance.save()

            return custom_response(
                success=True,
                message="Account created successfully.",
                data=AccountSerializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )

        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )