from rest_framework import serializers
from django.db.models import Sum, F
from .models import Customer
from sales.models import Sale

class CustomerSerializer(serializers.ModelSerializer):
    total_due = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    amount_type = serializers.SerializerMethodField()
    client_no = serializers.SerializerMethodField()
    total_sales = serializers.SerializerMethodField()
    advance_balance = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'email', 'address', 'is_active',
            'client_no', 'total_due', 'total_paid', 'amount_type',
            'company', 'total_sales', 'date_created', 'created_by',
            'advance_balance'  # 👈 Also added in the fields list
        ]
        read_only_fields = ['date_created', 'created_by']

    def get_advance_balance(self, obj):
        """Return stored advance directly from DB"""
        try:
            return float(obj.advance_balance) if obj.advance_balance is not None else 0.00
        except:
            return 0.00


    def get_client_no(self, obj):
        """Get client number - use existing or generate if missing"""
        if obj.client_no:
            return obj.client_no
        
        # Generate client number if missing
        try:
            last_customer = Customer.objects.filter(company=obj.company).order_by("-id").first()
            new_id = (last_customer.id + 1) if last_customer else 1
            return f"CU-{1000 + new_id}"
        except:
            return f"CU-{1000 + obj.id}" if obj.id else "CU-1000"

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
                
                total_due = float(total_due) if total_due is not None else 0.0
            
            return total_due
        except (TypeError, ValueError):
            return 0.00

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
                
                total_paid = float(total_paid) if total_paid is not None else 0.0
            
            return total_paid
        except (TypeError, ValueError):
            return 0.00

    def get_amount_type(self, obj):
        try:
            total_due = self.get_total_due(obj)
            return "Due" if total_due > 0 else "Paid"
        except (TypeError, ValueError):
            return "Paid"