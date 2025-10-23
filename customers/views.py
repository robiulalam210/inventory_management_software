from rest_framework import viewsets, status, serializers, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination  # Import your custom pagination
from .models import Customer
from .serializers import CustomerSerializer

# -----------------------------
# BaseCompanyViewSet
# -----------------------------
class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'  # override if needed
    pagination_class = CustomPageNumberPagination  # Add pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()

# -----------------------------
# Customer ViewSet
# -----------------------------
class CustomerViewSet(BaseCompanyViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    
    # Define search fields
    search_fields = ['name', 'phone', 'email', 'address']
    
    # Define filterset fields
    filterset_fields = {
        'status': ['exact', 'in'],
        'customer_type': ['exact'],
        'created_at': ['gte', 'lte', 'exact'],
    }
    
    # Define ordering fields
    ordering_fields = ['name', 'created_at', 'updated_at', 'total_purchases']
    ordering = ['name']  # Default ordering

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply additional filters from query parameters
        queryset = self.apply_filters(queryset)
        
        return queryset.order_by('name')

    def apply_filters(self, queryset):
        """
        Apply comprehensive filtering to customers queryset
        """
        params = self.request.GET
        
        # Search filter (handled by SearchFilter, but we can enhance it)
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(address__icontains=search) |
                Q(customer_id__icontains=search)
            )
        
        # Status filter
        status_filter = params.get('status')
        if status_filter:
            if status_filter.lower() == 'all':
                # Show all statuses
                pass
            else:
                queryset = queryset.filter(status=status_filter)
        
        # Customer type filter
        customer_type = params.get('customer_type')
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        
        # Date range filters
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            try:
                queryset = queryset.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                # Handle invalid date format
                pass
        
        # Min/Max purchases filter
        min_purchases = params.get('min_purchases')
        max_purchases = params.get('max_purchases')
        if min_purchases:
            try:
                queryset = queryset.filter(total_purchases__gte=float(min_purchases))
            except (ValueError, TypeError):
                pass
        if max_purchases:
            try:
                queryset = queryset.filter(total_purchases__lte=float(max_purchases))
            except (ValueError, TypeError):
                pass
        
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
            
            # Add filter summary to response
            response_data = {
                'data': serializer.data,
                'filters_applied': self.get_applied_filters_info(),
                'summary': self.get_customers_summary(queryset)
            }
            
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} customers",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching customers: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_applied_filters_info(self):
        """
        Return information about applied filters
        """
        params = self.request.GET
        applied_filters = {}
        
        filter_mapping = {
            'search': 'Search Term',
            'status': 'Status',
            'customer_type': 'Customer Type',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'min_purchases': 'Min Purchases',
            'max_purchases': 'Max Purchases',
            'ordering': 'Sort By',
        }
        
        for param, display_name in filter_mapping.items():
            value = params.get(param)
            if value:
                applied_filters[display_name] = value
        
        return applied_filters

    def get_customers_summary(self, queryset):
        """
        Get summary statistics for the filtered customers
        """
        try:
            from django.db.models import Count, Sum, Avg
            
            summary = queryset.aggregate(
                total_customers=Count('id'),
                active_customers=Count('id', filter=Q(status='active')),
                inactive_customers=Count('id', filter=Q(status='inactive')),
                total_purchase_amount=Sum('total_purchases'),
                average_purchase=Avg('total_purchases')
            )
            
            return {
                'total_customers': summary['total_customers'],
                'active_customers': summary['active_customers'] or 0,
                'inactive_customers': summary['inactive_customers'] or 0,
                'total_purchase_amount': float(summary['total_purchase_amount'] or 0),
                'average_purchase': float(summary['average_purchase'] or 0)
            }
        except Exception:
            return {}

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Customer details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching customer details: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = self.request.user
            company = getattr(user, 'company', None)

            # If staff, get company from staff profile
            if not company and hasattr(user, 'staff') and user.staff:
                company = getattr(user.staff, 'company', None)

            # role-based handling
            role = getattr(user, 'role', None)
            if role == 'staff' and not company:
                return custom_response(
                    success=False,
                    message="Staff user must belong to a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            instance = serializer.save(company=company)
            return custom_response(
                success=True,
                message="Customer created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            error_message = self.get_validation_error_message(e)
            return custom_response(
                success=False,
                message=error_message,
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
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return custom_response(
                success=True,
                message="Customer updated successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            error_message = self.get_validation_error_message(e)
            return custom_response(
                success=False,
                message=error_message,
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

    def get_validation_error_message(self, validation_error):
        """
        Extract meaningful validation error message
        """
        if hasattr(validation_error, 'detail'):
            if isinstance(validation_error.detail, dict):
                first_field = next(iter(validation_error.detail.keys()))
                first_error = validation_error.detail[first_field][0]
                return f"{first_field}: {first_error}"
            elif isinstance(validation_error.detail, list):
                return validation_error.detail[0]
        return "Validation error occurred"