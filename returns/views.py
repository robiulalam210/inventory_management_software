from rest_framework import viewsets, status, permissions, serializers
from core.utils import custom_response
from .models import SalesReturn, PurchaseReturn, BadStock
from .serializers import SalesReturnSerializer, PurchaseReturnSerializer, BadStockSerializer

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'  # override if needed

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()

# -----------------------------
# SalesReturn ViewSet
# -----------------------------
class SalesReturnViewSet(BaseCompanyViewSet):
    serializer_class = SalesReturnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return SalesReturn.objects.filter(company=user.company)
        return SalesReturn.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Sales returns fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Sales return details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            instance = serializer.save(company=company)
            return custom_response(
                success=True,
                message="Sales return created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
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

# -----------------------------
# PurchaseReturn ViewSet
# -----------------------------
class PurchaseReturnViewSet(BaseCompanyViewSet):
    serializer_class = PurchaseReturnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return PurchaseReturn.objects.filter(company=user.company)
        return PurchaseReturn.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Purchase returns fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Purchase return details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            instance = serializer.save(company=company)
            return custom_response(
                success=True,
                message="Purchase return created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
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

# -----------------------------
# BadStock ViewSet
# -----------------------------
class BadStockViewSet(BaseCompanyViewSet):
    serializer_class = BadStockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return BadStock.objects.filter(company=user.company)
        return BadStock.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Bad stocks fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Bad stock details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            instance = serializer.save(company=company)
            return custom_response(
                success=True,
                message="Bad stock created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
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