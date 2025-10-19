# core/base_viewsets.py
from rest_framework import viewsets
from rest_framework import serializers


class BaseCompanyViewSet(viewsets.ModelViewSet):
    """
    Base viewset that automatically filters by company and handles user authentication
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Check if user is authenticated
        if not user.is_authenticated:
            return queryset.none()
            
        # Check if user has a company
        if hasattr(user, 'company') and user.company:
            return queryset.filter(company=user.company)
        else:
            return queryset.none()

    def perform_create(self, serializer):
        """Automatically set company and created_by during creation"""
        user = self.request.user
        
        if not user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")
            
        if not hasattr(user, 'company') or not user.company:
            raise serializers.ValidationError("User does not have an associated company")
            
        serializer.save(company=user.company, created_by=user)