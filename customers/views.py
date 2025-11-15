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
        """
        Delete a customer - Only allow if no related records exist
        """
        try:
            instance = self.get_object()
            customer_name = instance.name
            
            # Check all possible relationships that might prevent deletion
            blocking_relationships = []
            
            def check_relationship(relationship_name, check_function):
                """Helper function to check relationships safely"""
                try:
                    count = check_function()
                    if count > 0:
                        blocking_relationships.append(f"{count} {relationship_name}")
                    return count
                except Exception as e:
                    logger.debug(f"Could not check {relationship_name}: {e}")
                    return 0
            
            # 1. Check sales
            sales_count = check_relationship("sales", lambda: 
                getattr(instance, 'sales').count() if hasattr(instance, 'sales') else
                getattr(instance, 'sale_set').count() if hasattr(instance, 'sale_set') else 0
            )
            
            # 2. Check money receipts
            money_receipts_count = check_relationship("money receipts", lambda: 
                getattr(instance, 'money_receipts').count() if hasattr(instance, 'money_receipts') else
                getattr(instance, 'moneyreceipt_set').count() if hasattr(instance, 'moneyreceipt_set') else 0
            )
            
            # 3. Direct database queries for common models
            # Sales
            if sales_count == 0:
                try:
                    from sales.models import Sale
                    sales_count = check_relationship("sales", 
                        lambda: Sale.objects.filter(customer=instance).count()
                    )
                except ImportError:
                    pass
            
            # Money Receipts
            if money_receipts_count == 0:
                try:
                    from transactions.models import MoneyReceipt
                    money_receipts_count = check_relationship("money receipts", 
                        lambda: MoneyReceipt.objects.filter(customer=instance).count()
                    )
                except ImportError:
                    pass
            
            # 4. Check other possible customer relationships
            # Due Collections
            try:
                from due_collections.models import DueCollection
                check_relationship("due collections",
                    lambda: DueCollection.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Invoices
            try:
                from invoices.models import Invoice
                check_relationship("invoices",
                    lambda: Invoice.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Payments
            try:
                from customer_payments.models import CustomerPayment
                check_relationship("customer payments",
                    lambda: CustomerPayment.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Statements
            try:
                from accounting.models import CustomerStatement
                check_relationship("customer statements",
                    lambda: CustomerStatement.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Ledger
            try:
                from ledger.models import CustomerLedger
                check_relationship("ledger entries",
                    lambda: CustomerLedger.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # 5. Generic check using Django's related objects
            try:
                for related_object in instance._meta.related_objects:
                    related_name = related_object.get_accessor_name()
                    try:
                        related_manager = getattr(instance, related_name)
                        if hasattr(related_manager, 'count'):
                            count = related_manager.count()
                            if count > 0:
                                # Only include if not already counted and it's a meaningful relationship
                                rel_name = related_name.replace('_set', '').replace('_', ' ')
                                if (not any(rel_name in rel for rel in blocking_relationships) and 
                                    any(keyword in related_name for keyword in ['sale', 'receipt', 'payment', 'invoice', 'due', 'ledger'])):
                                    blocking_relationships.append(f"{count} {rel_name}")
                    except Exception as e:
                        logger.debug(f"Could not check related object {related_name}: {e}")
            except Exception as e:
                logger.debug(f"Error checking generic related objects: {e}")
            
            # If any blocking relationships exist, mark as inactive instead of deleting
            if blocking_relationships:
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                
                # Create detailed message
                relationships_text = ", ".join(blocking_relationships)
                message = f"Customer cannot be deleted as it has transaction history ({relationships_text}). It has been marked as inactive instead."
                
                logger.warning(f"Customer deletion blocked for '{customer_name}'. Reasons: {blocking_relationships}")
                
                return custom_response(
                    success=True,
                    message=message,
                    data={
                        'is_active': instance.is_active,
                        'deletion_blocked': True,
                        'blocking_relationships': blocking_relationships,
                        'customer_id': instance.id,
                        'customer_name': customer_name
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # If no blocking relationships, proceed with actual deletion
            self.perform_destroy(instance)
            
            logger.info(f"Customer deleted successfully: {customer_name} (ID: {instance.id})")
            
            return custom_response(
                success=True,
                message=f"Customer '{customer_name}' deleted successfully.",
                data={
                    'deletion_successful': True,
                    'customer_name': customer_name
                },
                status_code=status.HTTP_200_OK
            )
                
        except Exception as e:
            logger.error(f"Error deleting customer: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
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
 