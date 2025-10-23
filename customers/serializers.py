from rest_framework import serializers
from django.db.models import Sum, Q, F
from .models import Customer
from sales.models import Sale

# -----------------------------
# Customer Serializer
# -----------------------------
class CustomerSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    total_due = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    amount_type = serializers.SerializerMethodField()
    client_no = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    total_sales = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'email', 'address', 'status', 'status_display', 
            'client_no', 'total_due', 'total_paid', 'amount_type', 'company', 
            'total_sales', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_client_no(self, obj):
        return f"CL-{1000 + obj.id}"

    def get_status_display(self, obj):
        """Get human-readable status"""
        return "Active" if obj.status else "Inactive"

    def get_total_sales(self, obj):
        """Get total number of sales for this customer"""
        # Use prefetched data if available
        if hasattr(obj, 'sales_count'):
            return obj.sales_count
        return obj.sales.count()

    def get_total_due(self, obj):
        """Calculate total due amount from sales"""
        # Use prefetched data if available
        if hasattr(obj, 'total_due_amount'):
            return f"{obj.total_due_amount:.2f}"
        
        # Fallback calculation
        total_due = Sale.objects.filter(
            customer=obj,
            company=obj.company
        ).aggregate(
            total_due=Sum(F('grand_total') - F('paid_amount'))
        )['total_due'] or 0
        
        # Ensure due amount is not negative
        return f"{max(total_due, 0):.2f}"

    def get_total_paid(self, obj):
        """Calculate total paid amount from sales"""
        # Use prefetched data if available
        if hasattr(obj, 'total_paid_amount'):
            return f"{obj.total_paid_amount:.2f}"
        
        # Fallback calculation
        total_paid = Sale.objects.filter(
            customer=obj,
            company=obj.company
        ).aggregate(
            total_paid=Sum('paid_amount')
        )['total_paid'] or 0
        
        return f"{total_paid:.2f}"

    def get_amount_type(self, obj):
        """Determine if customer has due or is paid"""
        # Use prefetched data if available
        if hasattr(obj, 'total_due_amount'):
            total_due = obj.total_due_amount
        else:
            total_due = float(self.get_total_due(obj))
        
        return "Due" if total_due > 0 else "Paid"