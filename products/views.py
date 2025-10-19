from rest_framework import viewsets, permissions, filters, status, serializers
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from django_filters import rest_framework as django_filters
from django.db import models
from core.base_viewsets import BaseCompanyViewSet
from .models import Product, Category, Unit, Brand, Group, Source
from .serializers import (
    ProductSerializer, CategorySerializer, UnitSerializer,
    BrandSerializer, GroupSerializer, SourceSerializer
)
from django.shortcuts import render, redirect
from django.db import models
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
import logging, traceback

from products.pagination import StandardResultsSetPagination
from .models import Product
from .serializers import ProductSerializer
from .filters import ProductFilter
from .base import BaseInventoryViewSet  # adjust import to your project layout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
    

# Import your project custom_response helper here. Replace the fallback below if needed.

from core.utils import custom_response

# Custom Filter for Product with Stock Status
class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name='category__id')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    product_name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    sku = django_filters.CharFilter(field_name='sku', lookup_expr='icontains')
    brand = django_filters.NumberFilter(field_name='brand__id')
    unit = django_filters.NumberFilter(field_name='unit__id')
    min_price = django_filters.NumberFilter(field_name='selling_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='selling_price', lookup_expr='lte')
    stock_status = django_filters.NumberFilter(method='filter_stock_status')
    
    class Meta:
        model = Product
        fields = ['category', 'brand', 'unit', 'group', 'source', 'is_active']
    
    def filter_stock_status(self, queryset, name, value):
        """
        Filter by stock status:
        0 = Out of stock (stock_qty == 0)
        1 = Low stock (stock_qty <= alert_quantity AND stock_qty > 0)
        2 = In stock (stock_qty > alert_quantity)
        """
        try:
            status_value = int(value)
            if status_value == 0:  # Out of stock
                return queryset.filter(stock_qty=0)
            elif status_value == 1:  # Low stock
                return queryset.filter(
                    stock_qty__gt=0, 
                    stock_qty__lte=models.F('alert_quantity')
                )
            elif status_value == 2:  # In stock
                return queryset.filter(stock_qty__gt=models.F('alert_quantity'))
        except (ValueError, TypeError):
            pass
        return queryset

# Base API ViewSet
class BaseInventoryViewSet(BaseCompanyViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

# Category ViewSet
class CategoryViewSet(BaseInventoryViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    filterset_fields = ['name']

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
                message="Category list fetched successfully.",
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
            
            # Check if user has company
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            company = request.user.company
            name = serializer.validated_data.get('name')
            
            if Category.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A category with this name already exists for this company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message="Category created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            logger.error("Validation error creating category: %s", e)
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error("Unhandled error creating product: %s", e)
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Unit ViewSet
class UnitViewSet(BaseInventoryViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code']

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
                message="Unit list fetched successfully.",
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
            
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            company = request.user.company
            name = serializer.validated_data.get('name')
            
            if Unit.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A unit with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message="Unit created successfully.",
                data=serializer.data,
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

# Brand ViewSet
class BrandViewSet(BaseInventoryViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    search_fields = ['name']
    ordering_fields = ['name']

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
                message="Brand list fetched successfully.",
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
            
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            company = request.user.company
            name = serializer.validated_data.get('name')
            
            if Brand.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A brand with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message="Brand created successfully.",
                data=serializer.data,
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

# Group ViewSet
class GroupViewSet(BaseInventoryViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    search_fields = ['name']
    ordering_fields = ['name']

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
                message="Group list fetched successfully.",
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
            
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            company = request.user.company
            name = serializer.validated_data.get('name')
            
            if Group.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A group with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message="Group created successfully.",
                data=serializer.data,
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

# Source ViewSet
class SourceViewSet(BaseInventoryViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    search_fields = ['name']
    ordering_fields = ['name']

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
                message="Source list fetched successfully.",
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
            
            if not hasattr(request.user, 'company') or not request.user.company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            company = request.user.company
            name = serializer.validated_data.get('name')
            
            if Source.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A source with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message="Source created successfully.",
                data=serializer.data,
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
        





class ProductViewSet(BaseInventoryViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = [
        'name', 'sku', 'description',
        'category__name', 'brand__name', 'unit__name',
        'group__name', 'source__name'
    ]
    ordering_fields = [
        'name', 'sku', 'selling_price', 'purchase_price',
        'stock_qty', 'created_at', 'updated_at'
    ]
    ordering = ['name']

    # Use the custom pagination class
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filter products by user's company with optimized queries"""
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return Product.objects.filter(company=user.company).select_related(
                'category', 'unit', 'brand', 'group', 'source', 'created_by'
            ).prefetch_related('category__products')
        return Product.objects.none()

    def _collect_filters(self, request, queryset):
        """
        Centralized filter application to avoid repeating code.
        Returns (queryset, filters_applied).
        """
        filters_applied = []

        category_id = request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category__id=category_id)
            filters_applied.append(f"category={category_id}")

        brand_id = request.query_params.get('brand_id')
        if brand_id:
            queryset = queryset.filter(brand__id=brand_id)
            filters_applied.append(f"brand={brand_id}")

        unit_id = request.query_params.get('unit_id')
        if unit_id:
            queryset = queryset.filter(unit__id=unit_id)
            filters_applied.append(f"unit={unit_id}")

        group_id = request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(group__id=group_id)
            filters_applied.append(f"group={group_id}")

        source_id = request.query_params.get('source_id')
        if source_id:
            queryset = queryset.filter(source__id=source_id)
            filters_applied.append(f"source={source_id}")

        product_name = request.query_params.get('product_name')
        if product_name:
            queryset = queryset.filter(name__icontains=product_name)
            filters_applied.append(f"name={product_name}")

        sku_search = request.query_params.get('sku')
        if sku_search:
            queryset = queryset.filter(sku__icontains=sku_search)
            filters_applied.append(f"sku={sku_search}")

        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(selling_price__gte=min_price)
            filters_applied.append(f"min_price={min_price}")
        if max_price:
            queryset = queryset.filter(selling_price__lte=max_price)
            filters_applied.append(f"max_price={max_price}")

        min_stock = request.query_params.get('min_stock')
        max_stock = request.query_params.get('max_stock')
        if min_stock:
            queryset = queryset.filter(stock_qty__gte=min_stock)
            filters_applied.append(f"min_stock={min_stock}")
        if max_stock:
            queryset = queryset.filter(stock_qty__lte=max_stock)
            filters_applied.append(f"max_stock={max_stock}")

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
                filters_applied.append("active=true")
            elif is_active.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)
                filters_applied.append("active=false")

        return queryset, filters_applied

    def list(self, request, *args, **kwargs):
        """
        Use DRF pagination and attach filters_applied to the paginated response.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())

            # apply filters
            queryset, filters_applied = self._collect_filters(request, queryset)

            # Let DRF pagination handle paging and slicing
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)

                # Insert filters_applied into the returned data dict
                data_with_filters = dict(paginated_response.data)
                data_with_filters['filters_applied'] = filters_applied

                return custom_response(
                    success=True,
                    message=f"Product list fetched successfully. {len(filters_applied)} filter(s) applied.",
                    data=data_with_filters,
                    status_code=status.HTTP_200_OK
                )

            # Fallback if pagination is not active
            serializer = self.get_serializer(queryset, many=True)
            response_data = {
                'results': serializer.data,
                'pagination': {
                    'count': len(serializer.data),
                    'total_pages': 1,
                    'current_page': 1,
                    'page_size': len(serializer.data),
                    'next': None,
                    'previous': None,
                    'from': 1 if serializer.data else 0,
                    'to': len(serializer.data),
                },
                'filters_applied': filters_applied
            }
            return custom_response(
                success=True,
                message=f"Product list fetched successfully. {len(filters_applied)} filter(s) applied.",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def advanced_search(self, request):
        """
        Advanced search with multiple criteria using DRF pagination.
        """
        try:
            queryset = self.get_queryset()

            # Text search
            search_term = request.query_params.get('q', '')
            if search_term:
                queryset = queryset.filter(
                    models.Q(name__icontains=search_term) |
                    models.Q(sku__icontains=search_term) |
                    models.Q(description__icontains=search_term)
                )

            # Multiple category filter (comma separated)
            categories = request.query_params.get('categories')
            if categories:
                category_list = [cat.strip() for cat in categories.split(',') if cat.strip()]
                if category_list:
                    queryset = queryset.filter(category__id__in=category_list)

            # Multiple brand filter
            brands = request.query_params.get('brands')
            if brands:
                brand_list = [brand.strip() for brand in brands.split(',') if brand.strip()]
                if brand_list:
                    queryset = queryset.filter(brand__id__in=brand_list)

            # Stock status filter
            stock_status = request.query_params.get('stock_status')
            if stock_status:
                try:
                    status_value = int(stock_status)
                    if status_value == 0:  # Out of stock
                        queryset = queryset.filter(stock_qty=0)
                    elif status_value == 1:  # Low stock
                        queryset = queryset.filter(
                            stock_qty__gt=0,
                            stock_qty__lte=models.F('alert_quantity')
                        )
                    elif status_value == 2:  # In stock
                        queryset = queryset.filter(stock_qty__gt=models.F('alert_quantity'))
                except (ValueError, TypeError):
                    pass

            # Price range
            min_price = request.query_params.get('min_price')
            max_price = request.query_params.get('max_price')
            if min_price:
                queryset = queryset.filter(selling_price__gte=min_price)
            if max_price:
                queryset = queryset.filter(selling_price__lte=max_price)

            # Stock range
            min_stock = request.query_params.get('min_stock')
            max_stock = request.query_params.get('max_stock')
            if min_stock:
                queryset = queryset.filter(stock_qty__gte=min_stock)
            if max_stock:
                queryset = queryset.filter(stock_qty__lte=max_stock)

            # Active status
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                if is_active.lower() in ['true', '1', 'yes']:
                    queryset = queryset.filter(is_active=True)
                elif is_active.lower() in ['false', '0', 'no']:
                    queryset = queryset.filter(is_active=False)

            # Ordering
            ordering = request.query_params.get('ordering', 'name')
            if ordering.lstrip('-') in [field for field in self.ordering_fields]:
                queryset = queryset.order_by(ordering)

            # Use pagination
            page = self.paginate_queryset(queryset)
            # Build a simple filters_applied list to return (include search_term and some applied criteria)
            filters_applied = []
            if search_term:
                filters_applied.append(f"q={search_term}")
            if categories:
                filters_applied.append(f"categories={categories}")
            if brands:
                filters_applied.append(f"brands={brands}")
            if stock_status:
                filters_applied.append(f"stock_status={stock_status}")

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                data_with_filters = dict(paginated_response.data)
                data_with_filters['filters_applied'] = filters_applied
                data_with_filters['search_term'] = search_term if search_term else None

                return custom_response(
                    success=True,
                    message="Advanced search completed successfully.",
                    data=data_with_filters,
                    status_code=status.HTTP_200_OK
                )

            serializer = self.get_serializer(queryset, many=True)
            response_data = {
                'results': serializer.data,
                'pagination': {
                    'count': len(serializer.data),
                    'total_pages': 1,
                    'current_page': 1,
                    'page_size': len(serializer.data),
                    'next': None,
                    'previous': None,
                    'from': 1 if serializer.data else 0,
                    'to': len(serializer.data),
                },
                'search_term': search_term if search_term else None,
                'filters_applied': filters_applied
            }
            return custom_response(
                success=True,
                message="Advanced search completed successfully.",
                data=response_data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Custom search endpoint for products using DRF pagination.
        """
        try:
            search_term = request.query_params.get('q', '')
            category_id = request.query_params.get('category_id')
            stock_status = request.query_params.get('stock_status')

            queryset = self.get_queryset()

            if search_term:
                queryset = queryset.filter(
                    models.Q(name__icontains=search_term) |
                    models.Q(sku__icontains=search_term) |
                    models.Q(description__icontains=search_term)
                )

            if category_id:
                queryset = queryset.filter(category__id=category_id)

            if stock_status:
                try:
                    status_value = int(stock_status)
                    if status_value == 0:  # Out of stock
                        queryset = queryset.filter(stock_qty=0)
                    elif status_value == 1:  # Low stock
                        queryset = queryset.filter(
                            stock_qty__gt=0,
                            stock_qty__lte=models.F('alert_quantity')
                        )
                    elif status_value == 2:  # In stock
                        queryset = queryset.filter(stock_qty__gt=models.F('alert_quantity'))
                except (ValueError, TypeError):
                    pass

            # Build small filters_applied
            filters_applied = []
            if search_term:
                filters_applied.append(f"q={search_term}")
            if category_id:
                filters_applied.append(f"category={category_id}")
            if stock_status:
                filters_applied.append(f"stock_status={stock_status}")

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                data_with_filters = dict(paginated_response.data)
                data_with_filters['filters_applied'] = filters_applied

                return custom_response(
                    success=True,
                    message="Products searched successfully.",
                    data=data_with_filters,
                    status_code=status.HTTP_200_OK
                )

            serializer = self.get_serializer(queryset, many=True)
            response_data = {
                'results': serializer.data,
                'pagination': {
                    'count': len(serializer.data),
                    'total_pages': 1,
                    'current_page': 1,
                    'page_size': len(serializer.data),
                    'next': None,
                    'previous': None,
                    'from': 1 if serializer.data else 0,
                    'to': len(serializer.data),
                },
                'filters_applied': filters_applied
            }

            return custom_response(
                success=True,
                message="Products searched successfully.",
                data=response_data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# # Product ViewSet with Stock Status Filtering
# class ProductViewSet(BaseInventoryViewSet):
#     queryset = Product.objects.all()
#     serializer_class = ProductSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_class = ProductFilter
#     search_fields = [
#         'name', 'sku', 'description',
#         'category__name', 'brand__name', 'unit__name', 
#         'group__name', 'source__name'
#     ]
#     ordering_fields = [
#         'name', 'sku', 'selling_price', 'purchase_price',
#         'stock_qty', 'created_at', 'updated_at'
#     ]
#     ordering = ['name']
    
#     # Remove pagination_class = None and use proper pagination
#     page_size = 20  # Default page size
#     page_size_query_param = 'page_size'
#     max_page_size = 100

#     def get_queryset(self):
#         """Filter products by user's company with optimized queries"""
#         user = self.request.user
#         if hasattr(user, 'company') and user.company:
#             return Product.objects.filter(company=user.company).select_related(
#                 'category', 'unit', 'brand', 'group', 'source', 'created_by'
#             ).prefetch_related('category__products')
#         return Product.objects.none()
    
#     def list(self, request, *args, **kwargs):
#         """
#         Enhanced list with multiple filters and pagination
#         """
#         try:
#             queryset = self.filter_queryset(self.get_queryset())
            
#             # Apply multiple filters from query parameters
#             filters_applied = []
            
#             # Category filter
#             category_id = request.query_params.get('category_id')
#             if category_id:
#                 queryset = queryset.filter(category__id=category_id)
#                 filters_applied.append(f"category={category_id}")
            
#             # Brand filter
#             brand_id = request.query_params.get('brand_id')
#             if brand_id:
#                 queryset = queryset.filter(brand__id=brand_id)
#                 filters_applied.append(f"brand={brand_id}")
            
#             # Unit filter
#             unit_id = request.query_params.get('unit_id')
#             if unit_id:
#                 queryset = queryset.filter(unit__id=unit_id)
#                 filters_applied.append(f"unit={unit_id}")
            
#             # Group filter
#             group_id = request.query_params.get('group_id')
#             if group_id:
#                 queryset = queryset.filter(group__id=group_id)
#                 filters_applied.append(f"group={group_id}")
            
#             # Source filter
#             source_id = request.query_params.get('source_id')
#             if source_id:
#                 queryset = queryset.filter(source__id=source_id)
#                 filters_applied.append(f"source={source_id}")
            
#             # Product name filter
#             product_name = request.query_params.get('product_name')
#             if product_name:
#                 queryset = queryset.filter(name__icontains=product_name)
#                 filters_applied.append(f"name={product_name}")
            
#             # SKU filter
#             sku_search = request.query_params.get('sku')
#             if sku_search:
#                 queryset = queryset.filter(sku__icontains=sku_search)
#                 filters_applied.append(f"sku={sku_search}")
            
#             # Price range filters
#             min_price = request.query_params.get('min_price')
#             max_price = request.query_params.get('max_price')
#             if min_price:
#                 queryset = queryset.filter(selling_price__gte=min_price)
#                 filters_applied.append(f"min_price={min_price}")
#             if max_price:
#                 queryset = queryset.filter(selling_price__lte=max_price)
#                 filters_applied.append(f"max_price={max_price}")
            
#             # Stock quantity filters
#             min_stock = request.query_params.get('min_stock')
#             max_stock = request.query_params.get('max_stock')
#             if min_stock:
#                 queryset = queryset.filter(stock_qty__gte=min_stock)
#                 filters_applied.append(f"min_stock={min_stock}")
#             if max_stock:
#                 queryset = queryset.filter(stock_qty__lte=max_stock)
#                 filters_applied.append(f"max_stock={max_stock}")
            
#             # Active status filter
#             is_active = request.query_params.get('is_active')
#             if is_active is not None:
#                 if is_active.lower() in ['true', '1', 'yes']:
#                     queryset = queryset.filter(is_active=True)
#                     filters_applied.append("active=true")
#                 elif is_active.lower() in ['false', '0', 'no']:
#                     queryset = queryset.filter(is_active=False)
#                     filters_applied.append("active=false")
            
#             # Get page size from request or use default
#             page_size = request.query_params.get('page_size', self.page_size)
#             try:
#                 page_size = int(page_size)
#                 if page_size > self.max_page_size:
#                     page_size = self.max_page_size
#             except (ValueError, TypeError):
#                 page_size = self.page_size
            
#             # Manual pagination implementation
#             page_number = request.query_params.get('page', 1)
#             try:
#                 page_number = int(page_number)
#             except (ValueError, TypeError):
#                 page_number = 1
            
#             # Calculate pagination
#             total_count = queryset.count()
#             total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
            
#             # Ensure page number is within valid range
#             if page_number < 1:
#                 page_number = 1
#             elif page_number > total_pages and total_pages > 0:
#                 page_number = total_pages
            
#             # Calculate start and end indices
#             start_index = (page_number - 1) * page_size
#             end_index = start_index + page_size
            
#             # Get paginated data
#             paginated_queryset = queryset[start_index:end_index]
            
#             serializer = self.get_serializer(paginated_queryset, many=True)
            
#             # Build pagination response
#             response_data = {
#                 'results': serializer.data,
#                 'pagination': {
#                     'count': total_count,
#                     'total_pages': total_pages,
#                     'current_page': page_number,
#                     'page_size': page_size,
#                     'next': None,
#                     'previous': None
#                 },
#                 'filters_applied': filters_applied
#             }
            
#             # Add next page URL
#             if page_number < total_pages:
#                 response_data['pagination']['next'] = f"?page={page_number + 1}&page_size={page_size}"
            
#             # Add previous page URL
#             if page_number > 1:
#                 response_data['pagination']['previous'] = f"?page={page_number - 1}&page_size={page_size}"
            
#             return custom_response(
#                 success=True,
#                 message=f"Product list fetched successfully. {len(filters_applied)} filter(s) applied.",
#                 data=response_data,
#                 status_code=status.HTTP_200_OK
#             )
            
#         except Exception as e:
#             return custom_response(
#                 success=False,
#                 message=str(e),
#                 data=None,
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     @action(detail=False, methods=['get'])
#     def advanced_search(self, request):
#         """
#         Advanced search with multiple criteria
#         """
#         try:
#             queryset = self.get_queryset()
            
#             # Text search
#             search_term = request.query_params.get('q', '')
#             if search_term:
#                 queryset = queryset.filter(
#                     models.Q(name__icontains=search_term) |
#                     models.Q(sku__icontains=search_term) |
#                     models.Q(description__icontains=search_term)
#                 )
            
#             # Multiple category filter (comma separated)
#             categories = request.query_params.get('categories')
#             if categories:
#                 category_list = [cat.strip() for cat in categories.split(',') if cat.strip()]
#                 if category_list:
#                     queryset = queryset.filter(category__id__in=category_list)
            
#             # Multiple brand filter
#             brands = request.query_params.get('brands')
#             if brands:
#                 brand_list = [brand.strip() for brand in brands.split(',') if brand.strip()]
#                 if brand_list:
#                     queryset = queryset.filter(brand__id__in=brand_list)
            
#             # Stock status filter
#             stock_status = request.query_params.get('stock_status')
#             if stock_status:
#                 try:
#                     status_value = int(stock_status)
#                     if status_value == 0:  # Out of stock
#                         queryset = queryset.filter(stock_qty=0)
#                     elif status_value == 1:  # Low stock
#                         queryset = queryset.filter(
#                             stock_qty__gt=0, 
#                             stock_qty__lte=models.F('alert_quantity')
#                         )
#                     elif status_value == 2:  # In stock
#                         queryset = queryset.filter(stock_qty__gt=models.F('alert_quantity'))
#                 except (ValueError, TypeError):
#                     pass
            
#             # Price range
#             min_price = request.query_params.get('min_price')
#             max_price = request.query_params.get('max_price')
#             if min_price:
#                 queryset = queryset.filter(selling_price__gte=min_price)
#             if max_price:
#                 queryset = queryset.filter(selling_price__lte=max_price)
            
#             # Stock range
#             min_stock = request.query_params.get('min_stock')
#             max_stock = request.query_params.get('max_stock')
#             if min_stock:
#                 queryset = queryset.filter(stock_qty__gte=min_stock)
#             if max_stock:
#                 queryset = queryset.filter(stock_qty__lte=max_stock)
            
#             # Active status
#             is_active = request.query_params.get('is_active')
#             if is_active is not None:
#                 if is_active.lower() in ['true', '1', 'yes']:
#                     queryset = queryset.filter(is_active=True)
#                 elif is_active.lower() in ['false', '0', 'no']:
#                     queryset = queryset.filter(is_active=False)
            
#             # Ordering
#             ordering = request.query_params.get('ordering', 'name')
#             if ordering.lstrip('-') in [field for field in self.ordering_fields]:
#                 queryset = queryset.order_by(ordering)
            
#             # Manual pagination for advanced search
#             page_size = request.query_params.get('page_size', 20)
#             try:
#                 page_size = int(page_size)
#                 if page_size > 100:  # Limit page size
#                     page_size = 100
#             except (ValueError, TypeError):
#                 page_size = 20
            
#             page_number = request.query_params.get('page', 1)
#             try:
#                 page_number = int(page_number)
#             except (ValueError, TypeError):
#                 page_number = 1
            
#             # Calculate pagination
#             total_count = queryset.count()
#             total_pages = (total_count + page_size - 1) // page_size
            
#             # Ensure valid page number
#             if page_number < 1:
#                 page_number = 1
#             elif page_number > total_pages and total_pages > 0:
#                 page_number = total_pages
            
#             # Get paginated data
#             start_index = (page_number - 1) * page_size
#             end_index = start_index + page_size
#             paginated_queryset = queryset[start_index:end_index]
            
#             serializer = self.get_serializer(paginated_queryset, many=True)
            
#             response_data = {
#                 'results': serializer.data,
#                 'pagination': {
#                     'count': total_count,
#                     'total_pages': total_pages,
#                     'current_page': page_number,
#                     'page_size': page_size,
#                     'next': None,
#                     'previous': None
#                 },
#                 'search_term': search_term if search_term else None
#             }
            
#             # Add next/previous page URLs
#             if page_number < total_pages:
#                 response_data['pagination']['next'] = f"?page={page_number + 1}&page_size={page_size}"
#             if page_number > 1:
#                 response_data['pagination']['previous'] = f"?page={page_number - 1}&page_size={page_size}"
            
#             return custom_response(
#                 success=True,
#                 message="Advanced search completed successfully.",
#                 data=response_data,
#                 status_code=status.HTTP_200_OK
#             )
            
#         except Exception as e:
#             return custom_response(
#                 success=False,
#                 message=str(e),
#                 data=None,
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     # Fix other methods that use pagination
#     @action(detail=False, methods=['get'])
#     def search(self, request):
#         """
#         Custom search endpoint for products
#         """
#         try:
#             search_term = request.query_params.get('q', '')
#             category_id = request.query_params.get('category_id')
#             stock_status = request.query_params.get('stock_status')
            
#             queryset = self.get_queryset()
            
#             if search_term:
#                 queryset = queryset.filter(
#                     models.Q(name__icontains=search_term) |
#                     models.Q(sku__icontains=search_term) |
#                     models.Q(description__icontains=search_term)
#                 )
            
#             if category_id:
#                 queryset = queryset.filter(category__id=category_id)
                
#             if stock_status:
#                 # Apply stock status filter
#                 try:
#                     status_value = int(stock_status)
#                     if status_value == 0:  # Out of stock
#                         queryset = queryset.filter(stock_qty=0)
#                     elif status_value == 1:  # Low stock
#                         queryset = queryset.filter(
#                             stock_qty__gt=0, 
#                             stock_qty__lte=models.F('alert_quantity')
#                         )
#                     elif status_value == 2:  # In stock
#                         queryset = queryset.filter(stock_qty__gt=models.F('alert_quantity'))
#                 except (ValueError, TypeError):
#                     pass
            
#             # Manual pagination for search
#             page_size = request.query_params.get('page_size', 20)
#             try:
#                 page_size = int(page_size)
#             except (ValueError, TypeError):
#                 page_size = 20
            
#             page_number = request.query_params.get('page', 1)
#             try:
#                 page_number = int(page_number)
#             except (ValueError, TypeError):
#                 page_number = 1
            
#             total_count = queryset.count()
#             total_pages = (total_count + page_size - 1) // page_size
            
#             if page_number < 1:
#                 page_number = 1
#             elif page_number > total_pages and total_pages > 0:
#                 page_number = total_pages
            
#             start_index = (page_number - 1) * page_size
#             end_index = start_index + page_size
#             paginated_queryset = queryset[start_index:end_index]
            
#             serializer = self.get_serializer(paginated_queryset, many=True)
            
#             response_data = {
#                 'results': serializer.data,
#                 'pagination': {
#                     'count': total_count,
#                     'total_pages': total_pages,
#                     'current_page': page_number,
#                     'page_size': page_size,
#                     'next': None if page_number >= total_pages else f"?page={page_number + 1}&page_size={page_size}",
#                     'previous': None if page_number <= 1 else f"?page={page_number - 1}&page_size={page_size}"
#                 }
#             }
            
#             return custom_response(
#                 success=True,
#                 message="Products searched successfully.",
#                 data=response_data,
#                 status_code=status.HTTP_200_OK
#             )
#         except Exception as e:
#             return custom_response(
#                 success=False,
#                 message=str(e),
#                 data=None,
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     # Keep your existing create, stock_info, low_stock, and filters methods...
#     # [Your existing create method remains the same]
#     # [Your existing stock_info method - update with manual pagination if needed]
#     # [Your existing low_stock method - update with manual pagination if needed]
#     # [Your existing filters method remains the same]