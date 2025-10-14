# products/views.py
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from core.base_viewsets import BaseCompanyViewSet  # ✅ BaseCompanyViewSet ইমপোর্ট
from .models import Product, Category, Unit, Brand, Group, Source
from .serializers import (
    ProductSerializer, CategorySerializer, UnitSerializer,
    BrandSerializer, GroupSerializer, SourceSerializer
)
from rest_framework import viewsets

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

# Category API
class CategoryViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def perform_create(self, serializer):   # ইউনিকনেস চেক করার জন্য ওভাররাইড      
        company = self.request.user.company
        name = serializer.validated_data.get('name')
        
        if Category.objects.filter(company=company, name=name).exists():
            raise serializers.ValidationError({"name": "A category with this name already exists"})
        
        serializer.save(company=company)


# Unit API
class UnitViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']

    def perform_create(self, serializer):   # ইউনিকনেস চেক করার জন্য ওভাররাইড
        company = self.request.user.company
        name = serializer.validated_data.get('name')

        if Unit.objects.filter(company=company, name=name).exists():
            raise serializers.ValidationError({"name": "A unit with this name already exists"})

        serializer.save(company=company)

    ordering_fields = ['name', 'code']

# Brand API
class BrandViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def perform_create(self, serializer):   # ইউনিকনেস চেক করার জন্য ওভাররাইড    
        company = self.request.user.company
        name = serializer.validated_data.get('name')
        
        if Brand.objects.filter(company=company, name=name).exists():
            raise serializers.ValidationError({"name": "A brand with this name already exists"})
        
        serializer.save(company=company)

# Group API
class GroupViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    def perform_create(self, serializer):   # ইউনিকনেস চেক করার জন্য ওভাররাইড    
        company = self.request.user.company
        name = serializer.validated_data.get('name')
        
        if Group.objects.filter(company=company, name=name).exists():
            raise serializers.ValidationError({"name": "A group with this name already exists"})
        
        serializer.save(company=company)

# Source API
class SourceViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

    def perform_create(self, serializer):   # ইউনিকনেস চেক করার জন্য ওভাররাইড    
        company = self.request.user.company
        name = serializer.validated_data.get('name')
        
        if Source.objects.filter(company=company, name=name).exists():
            raise serializers.ValidationError({"name": "A source with this name already exists"})
        
        serializer.save(company=company)

# Product API
class ProductViewSet(BaseCompanyViewSet):  # ✅ BaseCompanyViewSet থেকে ইনহেরিট
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
        return Product.objects.none()  # company না থাকলে কিছু দেখাবে না
    
    

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    