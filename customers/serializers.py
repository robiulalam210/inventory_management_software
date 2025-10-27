# customers/serializers.py
from rest_framework import serializers
from django.db.models import Sum, F
from .models import Customer
from sales.models import Sale

class CustomerSerializer(serializers.ModelSerializer):
    total_due = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    amount_type = serializers.SerializerMethodField()
    
    client_no = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    total_sales = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'address', 'is_active', 'status_display', 
            'client_no', 'total_due', 'total_paid', 'amount_type', 'company', 
            'total_sales', 'date_created'
        ]
        read_only_fields = ['date_created']

    def get_client_no(self, obj):
        return f"CL-{1000 + obj.id}"

    def get_status_display(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_total_sales(self, obj):
        if hasattr(obj, 'sales_count'):
            return obj.sales_count
        return obj.sale_set.count()  # Changed from sales to sale_set

    def get_total_due(self, obj):
        if hasattr(obj, 'total_due_amount'):
            return f"{obj.total_due_amount:.2f}"
        
        total_due = Sale.objects.filter(
            customer=obj,
            company=obj.company
        ).aggregate(
            total_due=Sum(F('grand_total') - F('paid_amount'))
        )['total_due'] or 0
        
        return f"{max(total_due, 0):.2f}"

    def get_total_paid(self, obj):
        if hasattr(obj, 'total_paid_amount'):
            return f"{obj.total_paid_amount:.2f}"
        
        total_paid = Sale.objects.filter(
            customer=obj,
            company=obj.company
        ).aggregate(
            total_paid=Sum('paid_amount')
        )['total_paid'] or 0
        
        return f"{total_paid:.2f}"

    def get_amount_type(self, obj):
        if hasattr(obj, 'total_due_amount'):
            total_due = obj.total_due_amount
        else:
            total_due = float(self.get_total_due(obj))
        
        return "Due" if total_due > 0 else "Paid"