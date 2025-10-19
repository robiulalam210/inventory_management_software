from rest_framework import serializers

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
    status = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'address', 'status', 'client_no',
            'total_due', 'total_paid', 'amount_type', 'company'
        ]

    def get_client_no(self, obj):
        return f"CL-{1000 + obj.id}"

    def get_status(self, obj):
        # You can customize status logic based on your business rules
        return 1  # Active

    def get_total_due(self, obj):
        # Calculate total due amount from sales
        from django.db.models import Sum, Q
        total_due = Sale.objects.filter(
            customer=obj,
            # Add your due calculation logic here
            # Example: Q(payment_status='due') | Q(payment_status='partial')
        ).aggregate(total_due=Sum('due_amount'))['total_due'] or 0
        return f"{total_due:.2f}"

    def get_total_paid(self, obj):
        # Calculate total paid amount from sales
        from django.db.models import Sum, Q
        total_paid = Sale.objects.filter(
            customer=obj,
            # Add your paid calculation logic here
            # Example: Q(payment_status='paid')
        ).aggregate(total_paid=Sum('paid_amount'))['total_paid'] or 0
        return f"{total_paid:.2f}"

    def get_amount_type(self, obj):
        # Determine if customer has due or is paid
        total_due = float(self.get_total_due(obj))
        if total_due > 0:
            return "Due"
        else:
            return "Paid"
