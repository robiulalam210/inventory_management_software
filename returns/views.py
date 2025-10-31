# returns/views.py
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from django.db.models import Q
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .models import SalesReturn, PurchaseReturn, BadStock
from .serializers import SalesReturnSerializer, PurchaseReturnSerializer, BadStockSerializer
from products.models import Product
from accounts.models import Account

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Data fetched successfully.",
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


class SalesReturnViewSet(BaseCompanyViewSet):
    serializer_class = SalesReturnSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = SalesReturn.objects.filter(company=user.company).prefetch_related('items')
        
        # Apply filters
        search = self.request.query_params.get('search', None)
        status_filter = self.request.query_params.get('status', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        customer_name = self.request.query_params.get('customer_name', None)
        
        if search:
            queryset = queryset.filter(
                Q(receipt_no__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(reason__icontains=search)
            )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if customer_name:
            queryset = queryset.filter(customer_name__icontains=customer_name)
            
        if start_date and end_date:
            queryset = queryset.filter(return_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(return_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(return_date__lte=end_date)
        
        return queryset.order_by('-return_date', '-id')

    @action(detail=False, methods=['get'])
    def get_initial_data(self, request):
        """Get initial data for sales return form"""
        try:
            user = request.user
            company = user.company
            
            # Get recent products and accounts
            products = Product.objects.filter(company=company).values('id', 'name', 'price')
            accounts = Account.objects.filter(company=company).values('id', 'name')
            
            data = {
                'products': list(products),
                'accounts': list(accounts),
            }
            
            return custom_response(
                success=True,
                message="Initial data fetched successfully.",
                data=data,
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
            instance = serializer.save(company=request.user.company)
            
            # Create bad stock entries for damaged items
            for item in instance.items.all():
                if item.damage_quantity > 0:
                    BadStock.objects.create(
                        product=item.product,
                        quantity=item.damage_quantity,
                        company=request.user.company,
                        reason=f"Damaged in sales return {instance.receipt_no}",
                        reference_type='sales_return',
                        reference_id=instance.id
                    )
            
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

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return custom_response(
                success=True,
                message="Sales return updated successfully.",
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
                message="Sales return deleted successfully.",
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


class PurchaseReturnViewSet(BaseCompanyViewSet):
    serializer_class = PurchaseReturnSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = PurchaseReturn.objects.filter(company=user.company).prefetch_related('items')
        
        # Apply filters
        search = self.request.query_params.get('search', None)
        status_filter = self.request.query_params.get('status', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        supplier = self.request.query_params.get('supplier', None)
        
        if search:
            queryset = queryset.filter(
                Q(invoice_no__icontains=search) |
                Q(supplier__icontains=search) |
                Q(reason__icontains=search)
            )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if supplier:
            queryset = queryset.filter(supplier__icontains=supplier)
            
        if start_date and end_date:
            queryset = queryset.filter(return_date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(return_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(return_date__lte=end_date)
        
        return queryset.order_by('-return_date', '-id')

    @action(detail=False, methods=['get'])
    def get_initial_data(self, request):
        """Get initial data for purchase return form"""
        try:
            user = request.user
            company = user.company
            
            # Get recent products and accounts
            products = Product.objects.filter(company=company).values('id', 'name', 'cost_price')
            accounts = Account.objects.filter(company=company).values('id', 'name')
            
            data = {
                'products': list(products),
                'accounts': list(accounts),
            }
            
            return custom_response(
                success=True,
                message="Initial data fetched successfully.",
                data=data,
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
            instance = serializer.save(company=request.user.company)
            
            # Create bad stock entries for returned items if needed
            for item in instance.items.all():
                BadStock.objects.create(
                    product=item.product,
                    quantity=item.quantity,
                    company=request.user.company,
                    reason=f"Returned from purchase {instance.invoice_no}",
                    reference_type='purchase_return',
                    reference_id=instance.id
                )
            
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


class BadStockViewSet(BaseCompanyViewSet):
    serializer_class = BadStockSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = BadStock.objects.filter(company=user.company).select_related('product')
        
        # Apply filters
        search = self.request.query_params.get('search', None)
        reference_type = self.request.query_params.get('reference_type', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search) |
                Q(reason__icontains=search)
            )
        
        if reference_type:
            queryset = queryset.filter(reference_type=reference_type)
            
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
        elif start_date:
            queryset = queryset.filter(date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset.order_by('-date', '-id')

    @action(detail=False, methods=['get'])
    def get_summary(self, request):
        """Get bad stock summary"""
        try:
            user = request.user
            company = user.company
            
            total_bad_stock = BadStock.objects.filter(company=company).count()
            total_quantity = BadStock.objects.filter(company=company).aggregate(
                total_quantity=models.Sum('quantity')
            )['total_quantity'] or 0
            
            by_reference_type = BadStock.objects.filter(company=company).values(
                'reference_type'
            ).annotate(
                count=models.Count('id'),
                total_quantity=models.Sum('quantity')
            )
            
            data = {
                'total_bad_stock': total_bad_stock,
                'total_quantity': total_quantity,
                'by_reference_type': list(by_reference_type)
            }
            
            return custom_response(
                success=True,
                message="Bad stock summary fetched successfully.",
                data=data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )