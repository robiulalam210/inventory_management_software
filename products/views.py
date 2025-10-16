from rest_framework import viewsets, permissions, filters, status, serializers
from django_filters.rest_framework import DjangoFilterBackend
from core.base_viewsets import BaseCompanyViewSet  # ✅ Custom base viewset
from .models import Product, Category, Unit, Brand, Group, Source
from .serializers import (
    ProductSerializer, CategorySerializer, UnitSerializer,
    BrandSerializer, GroupSerializer, SourceSerializer
)
from django.shortcuts import render, redirect

from core.utils import custom_response
from core.base_viewsets import BaseCompanyViewSet
from .froms import CategoryForm, UnitForm, BrandForm, GroupForm, SourceForm, ProductForm


# ----- Category API -----
class CategoryViewSet(BaseCompanyViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Category list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Category details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if Category.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A category with this name already exists for this company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            serializer.save(company=company)
            return custom_response(
                success=True,
                message="Category created successfully.",
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

# ----- Unit API -----
class UnitViewSet(BaseCompanyViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Unit list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Unit details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if Unit.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A unit with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            serializer.save(company=company)
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

# ----- Brand API -----
class BrandViewSet(BaseCompanyViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Brand list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Brand details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if Brand.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A brand with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            serializer.save(company=company)
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

# ----- Group API -----
class GroupViewSet(BaseCompanyViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Group list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Group details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if Group.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A group with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            serializer.save(company=company)
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

# ----- Source API -----
class SourceViewSet(BaseCompanyViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Source list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Source details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            if Source.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A source with this name already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            serializer.save(company=company)
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

# ----- Product API -----
class ProductViewSet(BaseCompanyViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'brand', 'unit', 'group', 'source']
    search_fields = ['name', 'sku', 'category__name', 'brand__name', 'unit__name', 'group__name', 'source__name']
    ordering_fields = ['name', 'selling_price', 'stock_qty', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.company:
            return Product.objects.filter(company=user.company).select_related(
                'category','unit','brand','group','source'
            )
        return Product.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return custom_response(
            success=True,
            message="Product list fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return custom_response(
            success=True,
            message="Product details fetched successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        import traceback
        import sys
        
        serializer = self.get_serializer(data=request.data)
        try:
            print("=== PRODUCT CREATE DEBUG ===")
            print(f"Request data: {request.data}")
            print(f"User: {request.user}")
            print(f"User company: {getattr(request.user, 'company', None)}")
            
            serializer.is_valid(raise_exception=True)
            company = getattr(self.request.user, "company", None)
            name = serializer.validated_data.get('name')
            
            print(f"Validated data: {serializer.validated_data}")
            
            if not company:
                return custom_response(
                    success=False,
                    message="User does not have an associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check for duplicate product name
            if Product.objects.filter(company=company, name=name).exists():
                return custom_response(
                    success=False,
                    message="A product with this name already exists for this company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            print("Saving product...")
            # Save the product
            product = serializer.save(company=company)
            print(f"Product saved successfully. ID: {product.id}, SKU: {product.sku}")
            
            return custom_response(
                success=True,
                message="Product created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
            
        except serializers.ValidationError as e:
            print(f"Validation Error: {e.detail}")
            return custom_response(
                success=False,
                message="Validation Error",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"=== EXCEPTION DETAILS ===")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception message: {str(e)}")
            print("=== TRACEBACK ===")
            traceback.print_exc(file=sys.stdout)
            print("=================")
            
            return custom_response(
                success=False,
                message=f"Internal server error: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Category
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'product/category_list.html', {'categories': categories})

def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'product/category_create.html', {'form': form})

# অনুরূপভাবে Unit, Brand, Group, Source, Product-এর জন্যও একইভাবে লিখুন:
def brand_list(request):
    brands = Brand.objects.all()
    return render(request, 'product/brand_list.html', {'brands': brands})

def brand_create(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('brand_list')
    else:
        form = BrandForm()
    return render(request, 'product/brand_create.html', {'form': form})

def product_list(request):
    products = Product.objects.all()
    return render(request, 'product/product_list.html', {'products': products})

def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'product/product_create.html', {'form': form})