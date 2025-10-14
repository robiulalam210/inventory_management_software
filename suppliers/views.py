from rest_framework import viewsets, status, permissions, serializers
from core.utils import custom_response
from .models import Supplier
from .serializers import SupplierSerializer

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

class SupplierViewSet(BaseCompanyViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return custom_response(
            success=True,
            message="Supplier list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        supplier = self.get_object()
        serializer = self.get_serializer(supplier)
        return custom_response(
            success=True,
            message="Supplier details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            instance = serializer.save(company=company)
            return custom_response(
                success=True,
                message="Supplier created successfully.",
                data=SupplierSerializer(instance).data,
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