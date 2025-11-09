import logging
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .models import Customer
from .serializers import CustomerSerializer

logger = logging.getLogger(__name__)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    search_fields = ['name', 'phone', 'email', 'address']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'date_created']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by company
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Customer.objects.none()
        
        # Apply custom filters
        queryset = self.apply_custom_filters(queryset)
        
        # Optimize queryset with annotations
        queryset = queryset.annotate(
            sales_count=Count('sale', distinct=True),
            total_paid_amount=Sum('sale__paid_amount'),
            total_due_amount=Sum('sale__grand_total') - Sum('sale__paid_amount')
        )
        
        return queryset

    def apply_custom_filters(self, queryset):
        params = self.request.GET
        
        # Search filter
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(address__icontains=search)
            )
        
        # Status filter
        status_filter = params.get('status')
        if status_filter:
            if status_filter.lower() == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter.lower() == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Date range filter
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date_created__date__range=[start_date, end_date])
        
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # If no pagination, return all results
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} customers",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error in CustomerViewSet list: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching customers: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = self.request.user
            company = getattr(user, 'company', None)

            if not company:
                return custom_response(
                    success=False,
                    message="User must belong to a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Check for duplicate phone number
            phone = serializer.validated_data.get('phone')
            if phone and Customer.objects.filter(company=company, phone=phone).exists():
                return custom_response(
                    success=False,
                    message="A customer with this phone number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            instance = serializer.save(company=company, created_by=user)
            return custom_response(
                success=True,
                message="Customer created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
    # Safely get the first error message
            if isinstance(e.detail, list) and e.detail:
                message = str(e.detail[0])
            elif isinstance(e.detail, dict) and e.detail:
                # Get first field error
                first_field = next(iter(e.detail.values()))
                if isinstance(first_field, list) and first_field:
                    message = str(first_field[0])
                else:
                    message = str(first_field)
            else:
                message = str(e.detail)
            
            return custom_response(
                success=False,
                message=message,
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

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            # Check for duplicate phone number (excluding current instance)
            phone = serializer.validated_data.get('phone')
            if phone and Customer.objects.filter(company=instance.company, phone=phone).exclude(id=instance.id).exists():
                return custom_response(
                    success=False,
                    message="A customer with this phone number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            self.perform_update(serializer)
            return custom_response(
                success=True,
                message="Customer updated successfully.",
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

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return custom_response(
                success=True,
                message="Customer deleted successfully.",
                data=None,
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        








class CustomerNonPaginationViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]  # Removed DjangoFilterBackend
    pagination_class = None  # Disable pagination
    
    search_fields = ['name', 'phone', 'email', 'address']
    ordering_fields = ['name', 'date_created']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by company only (no active/inactive filter)
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Customer.objects.none()
        
       
        
        # Optimize queryset with annotations
        queryset = queryset.annotate(
            sales_count=Count('sale', distinct=True),
            total_paid_amount=Sum('sale__paid_amount'),
            total_due_amount=Sum('sale__grand_total') - Sum('sale__paid_amount')
        )
        
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # No pagination - return all results
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} customers",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching customers: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 