# suppliers/serializers.py
import logging
import traceback
from rest_framework import serializers
from .models import Supplier
from purchases.models import Purchase

class SupplierSerializer(serializers.ModelSerializer):
    total_due = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    total_purchases = serializers.SerializerMethodField()
    purchase_count = serializers.SerializerMethodField()
    amount_type = serializers.SerializerMethodField()
    supplier_no = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    # Make company and created_by fields read-only as they will be set automatically
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'email', 'phone', 'address', 'status', 'supplier_no',
            'total_due', 'total_paid', 'total_purchases', 'purchase_count',
            'amount_type', 'company', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['company', 'created_by', 'supplier_no', 'created_at', 'updated_at']

    def get_supplier_no(self, obj):
        return obj.supplier_no or f"SUP-{1000 + obj.id}"

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_purchase_count(self, obj):
        """Get total number of purchases from this supplier"""
        purchase_count = Purchase.objects.filter(supplier=obj).count()
        return purchase_count

    def get_total_purchases(self, obj):
        """Get total purchases amount (grand total)"""
        from django.db.models import Sum
        total_purchases = Purchase.objects.filter(
            supplier=obj
        ).aggregate(total=Sum('grand_total'))['total'] or 0
        return float(total_purchases)

    def get_total_due(self, obj):
        """Calculate total due amount from purchases"""
        from django.db.models import Sum
        total_due = Purchase.objects.filter(
            supplier=obj
        ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0
        return float(total_due)

    def get_total_paid(self, obj):
        """Calculate total paid amount from purchases"""
        from django.db.models import Sum
        total_paid = Purchase.objects.filter(
            supplier=obj
        ).aggregate(total_paid=Sum('paid_amount'))['total_paid'] or 0
        return float(total_paid)

    def get_amount_type(self, obj):
        """Determine if supplier has due or is paid"""
        total_due = self.get_total_due(obj)
        if total_due > 0:
            return "Due"
        else:
            return "Paid"