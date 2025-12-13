# suppliers/serializers.py
import logging
from rest_framework import serializers
from .models import Supplier

logger = logging.getLogger(__name__)

class SupplierSerializer(serializers.ModelSerializer):
    amount_type = serializers.SerializerMethodField()
    
    # Make company and created_by fields read-only as they will be set automatically
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'email', 'phone', 'address', 'is_active', 'supplier_no',
            'total_due', 'total_paid', 'total_purchases', 'purchase_count',
            'advance_balance',  # SUCCESS: ADD THIS LINE - CRITICAL FIX
            'amount_type', 'company', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'company', 'created_by', 'supplier_no', 'created_at', 'updated_at',
            'total_due', 'total_paid', 'total_purchases', 'purchase_count',
            'advance_balance'  # SUCCESS: ADD THIS LINE
        ]

    def get_amount_type(self, obj):
        """Determine if supplier has due or is paid - ENHANCED VERSION"""
        if obj.total_due > 0:
            return "Due"
        elif obj.advance_balance > 0:
            return "Advance"  # SUCCESS: NEW: Show "Advance" when there's advance balance
        else:
            return "Paid"

class SupplierListSerializer(serializers.ModelSerializer):
    """Optimized serializer for list view"""
    amount_type = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'supplier_no', 'name', 'phone', 'address', 'is_active',
            'total_purchases', 'total_paid', 'total_due', 'purchase_count', 
            'advance_balance',  # SUCCESS: ADD THIS LINE
            'amount_type'
        ]

    def get_amount_type(self, obj):
        """Enhanced amount type that considers advance balance"""
        if obj.total_due > 0:
            return "Due"
        elif obj.advance_balance > 0:
            return "Advance"  # SUCCESS: NEW
        else:
            return "Paid"

class SupplierCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating suppliers"""
    class Meta:
        model = Supplier
        fields = ['name', 'email', 'phone', 'address', 'is_active']
        
    def validate_phone(self, value):
        """Validate phone number format"""
        if value and len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits")
        return value

    def validate(self, data):
        """Ensure at least one contact method is provided"""
        if not data.get('email') and not data.get('phone'):
            raise serializers.ValidationError("Either email or phone must be provided")
        return data