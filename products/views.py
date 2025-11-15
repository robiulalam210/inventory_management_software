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
from .serializers import ProductSerializer, ProductCreateSerializer, ProductUpdateSerializer
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
class BaseInventoryCRUDViewSet(BaseInventoryViewSet):
    """
    Base ViewSet for all inventory models with common CRUD operations
    """
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    filterset_fields = ['name', 'is_active']
    
    # These should be defined in subclasses
    model_class = None
    serializer_class = None
    
    # Customize these in subclasses if needed
    name_field = 'name'
    item_name = "Item"  # For messages - e.g., "Category", "Unit", etc.
    
    def get_queryset(self):
        """
        Override get_queryset to filter by company and handle active/inactive filtering
        """
        queryset = super().get_queryset()
        
        # Filter by user's company
        if hasattr(self.request.user, 'company') and self.request.user.company:
            queryset = queryset.filter(company=self.request.user.company)
        
        # Handle active/inactive filtering from URL parameters
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)
        
        return queryset

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
                message=f"{self.item_name} list fetched successfully.",
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
            name = serializer.validated_data.get(self.name_field)
            
            if self.model_class.objects.filter(company=company, **{self.name_field: name}).exists():
                return custom_response(
                    success=False,
                    message=f"A {self.item_name.lower()} with this {self.name_field} already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save(company=company, created_by=request.user)
            return custom_response(
                success=True,
                message=f"{self.item_name} created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            logger.error(f"Validation error creating {self.item_name.lower()}: {e}")
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unhandled error creating {self.item_name.lower()}: {e}")
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    def update(self, request, *args, **kwargs):
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            try:
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                
                return custom_response(
                    success=True,
                    message=f"{self.item_name} updated successfully.",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK,
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
    def destroy(self, request, *args, **kwargs):
        """
        Custom delete method that prevents deletion if item has products
        and instead marks it as inactive
        """
        try:
            instance = self.get_object()
            
            # Check if item has any products using common relationship patterns
            has_products = False
            
            # Try different possible relationship names
            relationship_patterns = ['products', 'product_set', f'{self.item_name.lower()}_products']
            
            for pattern in relationship_patterns:
                if hasattr(instance, pattern) and getattr(instance, pattern).exists():
                    has_products = True
                    break
            
            # If no specific relationship found, try a more generic approach
            if not has_products:
                # Check if there are any products referencing this instance
                try:
                    from .models import Product
                    if self.model_class == Category:
                        has_products = Product.objects.filter(category=instance).exists()
                    elif self.model_class == Unit:
                        has_products = Product.objects.filter(unit=instance).exists()
                    elif self.model_class == Brand:
                        has_products = Product.objects.filter(brand=instance).exists()
                    elif self.model_class == Group:
                        has_products = Product.objects.filter(group=instance).exists()
                    elif self.model_class == Source:
                        has_products = Product.objects.filter(source=instance).exists()
                except Exception:
                    pass
            
            if has_products:
                # Instead of deleting, mark as inactive
                instance.is_active = False
                instance.save()
                
                return custom_response(
                    success=True,
                    message=f"{self.item_name} has associated products. It has been marked as inactive instead of deleted.",
                    data=None,
                    status_code=status.HTTP_200_OK
                )
            
            # If no products, proceed with actual deletion
            instance.delete()
            return custom_response(
                success=True,
                message=f"{self.item_name} deleted successfully.",
                data=None,
                status_code=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            logger.error(f"Error deleting {self.item_name.lower()}: {e}")
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
        

    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Custom endpoint to get only active items
        """
        try:
            queryset = self.get_queryset().filter(is_active=True)
            queryset = self.filter_queryset(queryset)
            
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Active {self.item_name.lower()}s fetched successfully.",
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

    @action(detail=False, methods=['get'])
    def inactive(self, request):
        """
        Custom endpoint to get only inactive items
        """
        try:
            queryset = self.get_queryset().filter(is_active=False)
            queryset = self.filter_queryset(queryset)
            
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Inactive {self.item_name.lower()}s fetched successfully.",
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

# Category ViewSet
class CategoryViewSet(BaseInventoryCRUDViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name', 'description']  # Override if needed
    model_class = Category
    item_name = "Category"

# Unit ViewSet
class UnitViewSet(BaseInventoryCRUDViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    search_fields = ['name', 'code']  # Override if needed
    ordering_fields = ['name', 'code']  # Override if needed
    model_class = Unit
    item_name = "Unit"

# Brand ViewSet
class BrandViewSet(BaseInventoryCRUDViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    model_class = Brand
    item_name = "Brand"

# Group ViewSet
class GroupViewSet(BaseInventoryCRUDViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    model_class = Group
    item_name = "Group"

# Source ViewSet
class SourceViewSet(BaseInventoryCRUDViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    model_class = Source
    item_name = "Source"


    
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
        'stock_qty', 'created_at', 'updated_at', 'is_active'
    ]
    ordering = ['sku']
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ProductCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProductUpdateSerializer
        return ProductSerializer

    @action(detail=False, methods=['get'], url_path='barcode-search')
    def barcode_search(self, request):
        """
        Search a product by barcode/SKU for the logged-in user's company
        Example: GET /api/products/barcode-search/?sku=PDT-1-00001
        """
        sku = request.query_params.get('sku') or request.query_params.get('barcode')
        if not sku:
            return Response({'detail': 'SKU or barcode is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = getattr(request.user, 'company', None)
            queryset = self.get_queryset()
            if company:
                queryset = queryset.filter(company=company)

            product = queryset.filter(sku__iexact=sku).first()
            if not product:
                return Response({'detail': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

            serializer = self.get_serializer(product)
            return   custom_response(
                success=True,
                message="Product details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_queryset(self):
        """Filter products by user's company with optimized queries"""
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            return Product.objects.filter(company=user.company).select_related(
                'category', 'unit', 'brand', 'group', 'source', 'created_by'
            ).prefetch_related('category__products')
        return Product.objects.none()

    def retrieve(self, request, *args, **kwargs):
        """
        Get single product details
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return custom_response(
                success=True,
                message="Product details fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Product.DoesNotExist:
            return custom_response(
                success=False,
                message="Product not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        """
        Create a new product
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Set company and created_by
            product = serializer.save(
                company=request.user.company,
                created_by=request.user
            )
            
            # Return the created product with full details
            full_serializer = ProductSerializer(product)
            return custom_response(
                success=True,
                message="Product created successfully.",
                data=full_serializer.data,
                status_code=status.HTTP_201_CREATED
            )
            
        except serializers.ValidationError as e:
            # SIMPLIFIED ERROR EXTRACTION - Return clean message
            error_message = "Validation error"
            
            if isinstance(e.detail, dict):
                # Extract the first error message from any field
                for field, errors in e.detail.items():
                    if isinstance(errors, list) and errors:
                        error_message = str(errors[0])  # Get first error
                        break
                    elif errors:
                        error_message = str(errors)
                        break
            elif isinstance(e.detail, list) and e.detail:
                error_message = str(e.detail[0])
            else:
                error_message = str(e.detail)
            
            return custom_response(
                success=False,
                message=error_message,  # Clean, simple message
                data=None,  # Don't send complex error data to frontend
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
        """
        Update an existing product
        """
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            
            product = serializer.save()
            
            # Return the updated product with full details
            full_serializer = ProductSerializer(product)
            return custom_response(
                success=True,
                message="Product updated successfully.",
                data=full_serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Product.DoesNotExist:
            return custom_response(
                success=False,
                message="Product not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation error",
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

    def partial_update(self, request, *args, **kwargs):
        """
        Partial update of a product
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a product - Only allow if no sales or purchases
        """
        try:
            instance = self.get_object()
            product_name = instance.name
            product_id = instance.id
            
            logger.info(f"Attempting to delete product: {product_name} (ID: {product_id})")
            
            # PROPER relationship checking - only check reverse relationships
            has_sales = False
            has_purchases = False
            has_stock_movements = False
            
            sales_count = 0
            purchases_count = 0
            stock_movements_count = 0
            
            # Check only reverse relationships (related_name accessors)
            logger.info("Checking reverse relationships...")
            
            # Method 1: Check common relationship names
            common_relationships = {
                'sale_items': ('sales', has_sales, sales_count),
                'saleitem_set': ('sales', has_sales, sales_count),
                'purchase_items': ('purchases', has_purchases, purchases_count),
                'purchaseitem_set': ('purchases', has_purchases, purchases_count),
                'stock_movements': ('stock movements', has_stock_movements, stock_movements_count),
                'stockmovement_set': ('stock movements', has_stock_movements, stock_movements_count),
            }
            
            for rel_name, (rel_type, has_flag, count_var) in common_relationships.items():
                if hasattr(instance, rel_name):
                    try:
                        related_manager = getattr(instance, rel_name)
                        current_count = related_manager.count()
                        logger.info(f"Relationship '{rel_name}': {current_count} records")
                        
                        if current_count > 0:
                            if rel_type == 'sales':
                                has_sales = True
                                sales_count = current_count
                            elif rel_type == 'purchases':
                                has_purchases = True
                                purchases_count = current_count
                            elif rel_type == 'stock movements':
                                has_stock_movements = True
                                stock_movements_count = current_count
                    except Exception as e:
                        logger.warning(f"Error checking relationship '{rel_name}': {e}")
            
            # Method 2: Direct database queries (most reliable)
            logger.info("Performing direct database queries...")
            
            # Check sales
            try:
                from sales.models import SaleItem
                direct_sales_count = SaleItem.objects.filter(product=instance).count()
                logger.info(f"Direct SaleItem query: {direct_sales_count} records")
                if direct_sales_count > 0:
                    has_sales = True
                    sales_count = direct_sales_count
            except ImportError:
                logger.warning("SaleItem model not found in sales app")
            except Exception as e:
                logger.warning(f"Error querying SaleItem: {e}")
            
            # Check purchases
            try:
                from purchases.models import PurchaseItem
                direct_purchases_count = PurchaseItem.objects.filter(product=instance).count()
                logger.info(f"Direct PurchaseItem query: {direct_purchases_count} records")
                if direct_purchases_count > 0:
                    has_purchases = True
                    purchases_count = direct_purchases_count
            except ImportError:
                logger.warning("PurchaseItem model not found in purchases app")
            except Exception as e:
                logger.warning(f"Error querying PurchaseItem: {e}")
            
            # Check stock movements
            try:
                from inventory.models import StockMovement
                direct_stock_count = StockMovement.objects.filter(product=instance).count()
                logger.info(f"Direct StockMovement query: {direct_stock_count} records")
                if direct_stock_count > 0:
                    has_stock_movements = True
                    stock_movements_count = direct_stock_count
            except ImportError:
                logger.warning("StockMovement model not found")
            except Exception as e:
                logger.warning(f"Error querying StockMovement: {e}")
            
            logger.info(f"Final check - Sales: {has_sales} ({sales_count}), Purchases: {has_purchases} ({purchases_count}), Stock: {has_stock_movements} ({stock_movements_count})")
            
            # Decision: Delete or deactivate
            if has_sales or has_purchases or has_stock_movements:
                # Instead of deleting, mark as inactive
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                
                # Build detailed message
                reasons = []
                if has_sales:
                    reasons.append(f"{sales_count} sales")
                if has_purchases:
                    reasons.append(f"{purchases_count} purchases")
                if has_stock_movements:
                    reasons.append(f"{stock_movements_count} stock movements")
                
                message = f"Product cannot be deleted as it has {', '.join(reasons)}. It has been marked as inactive instead."
                
                logger.info(f"Product {product_name} marked as inactive. Reason: {message}")
                
                return custom_response(
                    success=True,
                    message=message,
                    data={
                        'is_active': instance.is_active,
                        'deletion_blocked': True,
                        'blocking_reasons': reasons
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # If no transactions, proceed with actual deletion
            instance.delete()
            logger.info(f"Product {product_name} (ID: {product_id}) successfully deleted")
            
            return custom_response(
                success=True,
                message=f"Product '{product_name}' deleted successfully.",
                data=None,
                status_code=status.HTTP_200_OK
            )
                
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            logger.error(traceback.format_exc())
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """
        Toggle product active status
        """
        try:
            product = self.get_object()
            product.is_active = not product.is_active
            product.save(update_fields=['is_active'])
            
            return custom_response(
                success=True,
                message=f"Product {'activated' if product.is_active else 'deactivated'} successfully.",
                data={'is_active': product.is_active},
                status_code=status.HTTP_200_OK
            )
            
        except Product.DoesNotExist:
            return custom_response(
                success=False,
                message="Product not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def stock_history(self, request, pk=None):
        """
        Get stock history for a product
        """
        try:
            product = self.get_object()
            # Assuming you have a StockHistory model
            stock_history = product.stock_history.all().order_by('-created_at')
            
            # You would need a StockHistorySerializer
            from .serializers import StockHistorySerializer
            serializer = StockHistorySerializer(stock_history, many=True)
            
            return custom_response(
                success=True,
                message="Stock history fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Product.DoesNotExist:
            return custom_response(
                success=False,
                message="Product not found.",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        Supports both paginated and non-paginated responses based on query parameter.
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.filter_queryset(self.get_queryset())

            # apply filters
            queryset, filters_applied = self._collect_filters(request, queryset)

            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                response_data = {
                    'results': serializer.data,
                    'count': len(serializer.data),
                    'filters_applied': filters_applied,
                    'pagination': 'disabled'
                }
                return custom_response(
                    success=True,
                    # message=f"Product list fetched successfully (no pagination). {len(filters_applied)} filter(s) applied.",
                    data= serializer.data,
                    status_code=status.HTTP_200_OK
                )

            # Use DRF pagination for paginated response
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
    def active(self, request):
        """
        Get only active products with pagination control
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.get_queryset().filter(is_active=True)
            queryset = self.filter_queryset(queryset)
            
            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                return custom_response(
                    success=True,
                    message=f"Active products fetched successfully (no pagination). Total: {queryset.count()}",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            
            # Paginated response
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
                
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Active products fetched successfully.",
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

    @action(detail=False, methods=['get'])
    def inactive(self, request):
        """
        Get only inactive products with pagination control
        """
        try:
            # Check if pagination should be disabled
            no_pagination = request.query_params.get('no_pagination', '').lower() in ['true', '1', 'yes']
            
            queryset = self.get_queryset().filter(is_active=False)
            queryset = self.filter_queryset(queryset)
            
            # Handle non-paginated response
            if no_pagination:
                serializer = self.get_serializer(queryset, many=True)
                return custom_response(
                    success=True,
                    message=f"Inactive products fetched successfully (no pagination). Total: {queryset.count()}",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )
            
            # Paginated response
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
                
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message="Inactive products fetched successfully.",
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

 

