from rest_framework import serializers
from .models import MoneyReceipt
from sales.models import Sale
from customers.models import Customer
from accounts.models import Account
class MoneyReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)
    sale_invoice_no = serializers.CharField(source='sale.invoice_no', read_only=True, allow_null=True)

    class Meta:
        model = MoneyReceipt
        fields = [
            'id', 'mr_no', 'customer', 'customer_name', 'customer_phone',
            'amount', 'payment_method', 'payment_date', 'remark', 'account', 'sale', 'sale_invoice_no',
            'seller', 'seller_name', 'cheque_status', 'cheque_id'
        ]
        read_only_fields = ['mr_no', 'customer_name', 'customer_phone', 'sale_invoice_no', 'seller_name']

    def create(self, validated_data):
        # Update sale(s) due/paid amounts if relevant
        sale = validated_data.get("sale", None)
        customer = validated_data["customer"]
        amount = validated_data["amount"]

        # If single sale
        if sale:
            sale.paid_amount += amount
            sale.due_amount = max(0, sale.payable_amount - sale.paid_amount)
            sale.save(update_fields=['paid_amount', 'due_amount'])
        else:
            # Pay all dues for this customer (applies amount in FIFO order)
            remaining = amount
            for s in Sale.objects.filter(customer=customer, due_amount__gt=0).order_by("sale_date"):
                pay = min(remaining, s.due_amount)
                s.paid_amount += pay
                s.due_amount -= pay
                s.save(update_fields=['paid_amount', 'due_amount'])
                remaining -= pay
                if remaining <= 0:
                    break

        return super().create(validated_data)