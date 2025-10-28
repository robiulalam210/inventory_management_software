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
            'id', 'name', 'phone', 'email', 'address', 'is_active', 'status_display', 
            'client_no', 'total_due', 'total_paid', 'amount_type', 'company', 
            'total_sales', 'date_created', 'created_by'
        ]
        read_only_fields = ['date_created', 'created_by']

    def get_client_no(self, obj):
        return f"CL-{1000 + obj.id}"

    def get_status_display(self, obj):
        return "Active" if obj.is_active else "Inactive"

    def get_total_sales(self, obj):
        if hasattr(obj, 'sales_count'):
            return obj.sales_count
        return obj.sale_set.count()

    def get_total_due(self, obj):
        try:
            if hasattr(obj, 'total_due_amount') and obj.total_due_amount is not None:
                total_due = float(obj.total_due_amount)
            else:
                total_due = Sale.objects.filter(
                    customer=obj,
                    company=obj.company
                ).aggregate(
                    total_due=Sum(F('grand_total') - F('paid_amount'))
                )['total_due'] or 0
                
                # Ensure total_due is not None
                total_due = float(total_due) if total_due is not None else 0.0
            
            return f"{max(total_due, 0):.2f}"
        except (TypeError, ValueError):
            return "0.00"

    def get_total_paid(self, obj):
        try:
            if hasattr(obj, 'total_paid_amount') and obj.total_paid_amount is not None:
                total_paid = float(obj.total_paid_amount)
            else:
                total_paid = Sale.objects.filter(
                    customer=obj,
                    company=obj.company
                ).aggregate(
                    total_paid=Sum('paid_amount')
                )['total_paid'] or 0
                
                # Ensure total_paid is not None
                total_paid = float(total_paid) if total_paid is not None else 0.0
            
            return f"{total_paid:.2f}"
        except (TypeError, ValueError):
            return "0.00"

    def get_amount_type(self, obj):
        try:
            total_due_str = self.get_total_due(obj)
            total_due = float(total_due_str) if total_due_str else 0.0
            return "Due" if total_due > 0 else "Paid"
        except (TypeError, ValueError):
            return "Paid"