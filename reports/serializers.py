# reports/serializers.py
from rest_framework import serializers
from expenses.models import Expense

# --------------------
# Filter Serializers
# --------------------
class DateRangeFilterSerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    range = serializers.CharField(required=False)

class SalesReportFilterSerializer(DateRangeFilterSerializer):
    customer = serializers.IntegerField(required=False)
    payment_status = serializers.CharField(required=False)
    sale_type = serializers.CharField(required=False)
    invoice_no = serializers.CharField(required=False)
    min_amount = serializers.FloatField(required=False)
    max_amount = serializers.FloatField(required=False)

class PurchaseReportFilterSerializer(DateRangeFilterSerializer):
    supplier = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    payment_status = serializers.CharField(required=False)
    invoice_no = serializers.CharField(required=False)
    min_amount = serializers.FloatField(required=False)
    max_amount = serializers.FloatField(required=False)

class ExpenseFilterSerializer(DateRangeFilterSerializer):
    category = serializers.IntegerField(required=False)
    payment_method = serializers.CharField(required=False)
    min_amount = serializers.FloatField(required=False)
    max_amount = serializers.FloatField(required=False)

class StockFilterSerializer(serializers.Serializer):
    category = serializers.IntegerField(required=False)
    min_stock = serializers.IntegerField(required=False)
    max_stock = serializers.IntegerField(required=False)
    threshold = serializers.IntegerField(required=False)

class SupplierDueAdvanceFilterSerializer(DateRangeFilterSerializer):
    supplier = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(
        choices=[('due', 'Due'), ('advance', 'Advance'), ('all', 'All')],
        required=False,
        default='all'
    )

class SupplierLedgerFilterSerializer(DateRangeFilterSerializer):
    supplier = serializers.IntegerField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=[('all', 'All'), ('purchase', 'Purchase'), ('payment', 'Payment'), ('return', 'Return')],
        required=False,
        default='all'
    )

class CustomerDueAdvanceFilterSerializer(DateRangeFilterSerializer):
    customer = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(
        choices=[('due', 'Due'), ('advance', 'Advance'), ('all', 'All')],
        required=False,
        default='all'
    )

class CustomerLedgerFilterSerializer(DateRangeFilterSerializer):
    customer = serializers.IntegerField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=[('all', 'All'), ('sale', 'Sale'), ('payment', 'Payment'), ('return', 'Return')],
        required=False,
        default='all'
    )

# --------------------
# Report Serializers
# --------------------
class SalesReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    invoice_no = serializers.CharField()
    sale_date = serializers.DateField()
    customer_name = serializers.CharField()
    sales_by = serializers.CharField()
    sales_price = serializers.FloatField()
    cost_price = serializers.FloatField()
    profit = serializers.FloatField()
    collect_amount = serializers.FloatField()
    due_amount = serializers.FloatField()
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    payment_status = serializers.CharField(required=False)
    sale_type = serializers.CharField(required=False)

class PurchaseReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    invoice_no = serializers.CharField()
    purchase_date = serializers.DateField()
    supplier = serializers.CharField()
    net_total = serializers.FloatField()
    paid_total = serializers.FloatField()
    due_total = serializers.FloatField()
    supplier_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.CharField(required=False)
    payment_status = serializers.CharField(required=False)
    location = serializers.CharField(required=False)

class ProfitLossReportSerializer(serializers.Serializer):
    total_sales = serializers.FloatField()
    total_purchase = serializers.FloatField()
    total_expenses = serializers.FloatField()
    gross_profit = serializers.FloatField()
    net_profit = serializers.FloatField()
    expense_breakdown = serializers.ListField(required=False)
    date_range = serializers.DictField(required=False)


# serializers.py - Add this serializer
class PurchaseReturnReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    invoice_no = serializers.CharField()
    supplier = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    return_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateField()

    
class SalesReturnReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    invoice_no = serializers.CharField()
    customer = serializers.CharField()
    total_amount = serializers.FloatField()
    return_amount = serializers.FloatField()
    date = serializers.DateField()

class TopSoldProductsSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    product_name = serializers.CharField()
    selling_price = serializers.FloatField()
    total_sold_quantity = serializers.IntegerField()
    total_sold_price = serializers.FloatField()
    product_id = serializers.IntegerField(required=False)

class LowStockSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    product_name = serializers.CharField()
    selling_price = serializers.FloatField()
    alert_quantity = serializers.IntegerField()
    total_stock_quantity = serializers.IntegerField()
    total_sold_quantity = serializers.IntegerField()
    product_id = serializers.IntegerField(required=False)
    category = serializers.CharField(required=False)
    brand = serializers.CharField(required=False)

class BadStockReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    product = serializers.CharField()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()

class StockReportSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    product_no = serializers.IntegerField(source='product_id')
    product_name = serializers.CharField()
    category = serializers.CharField()
    brand = serializers.CharField()
    avg_purchase_price = serializers.FloatField()
    selling_price = serializers.FloatField()
    current_stock = serializers.IntegerField()
    value = serializers.FloatField()

class ExpenseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    head = serializers.CharField(source='head.name')
    subhead = serializers.CharField(source='subhead.name', allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.CharField()
    expense_date = serializers.DateField()
    note = serializers.CharField(allow_null=True)

class ReportSummarySerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    total_discount = serializers.FloatField()
    total_vat = serializers.FloatField()
    date_range = serializers.DictField()

class SupplierDueAdvanceSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    supplier_no = serializers.IntegerField(source='supplier_id')
    supplier_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    present_due = serializers.FloatField()
    present_advance = serializers.FloatField()
    supplier_id = serializers.IntegerField()

class SupplierLedgerSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    voucher_no = serializers.CharField()
    date = serializers.DateField()
    particular = serializers.CharField()
    details = serializers.CharField()
    type = serializers.CharField()
    method = serializers.CharField()
    debit = serializers.FloatField()
    credit = serializers.FloatField()
    due = serializers.FloatField()
    supplier_id = serializers.IntegerField()
    supplier_name = serializers.CharField()

class CustomerDueAdvanceSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    customer_no = serializers.IntegerField(source='customer_id')
    customer_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    present_due = serializers.FloatField()
    present_advance = serializers.FloatField()
    customer_id = serializers.IntegerField()

class CustomerLedgerSerializer(serializers.Serializer):
    sl = serializers.IntegerField()
    voucher_no = serializers.CharField()
    date = serializers.DateField()
    particular = serializers.CharField()
    details = serializers.CharField()
    type = serializers.CharField()
    method = serializers.CharField()
    debit = serializers.FloatField()
    credit = serializers.FloatField()
    due = serializers.FloatField()
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()