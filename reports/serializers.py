from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from expenses.models import Expense
from expenses.serializers import ExpenseSerializer
# --------------------
# Sales Report Serializer
# --------------------
class SalesReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    customer = serializers.CharField()
    total_amount = serializers.FloatField()
    total_discount = serializers.FloatField()
    total_vat = serializers.FloatField()
    net_amount = serializers.FloatField()
    date = serializers.DateField()

# --------------------
# Purchase Report Serializer
# --------------------
class PurchaseReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    supplier = serializers.CharField()
    total_amount = serializers.FloatField()
    total_discount = serializers.FloatField()
    net_amount = serializers.FloatField()
    date = serializers.DateField()

# --------------------
# Profit & Loss Report Serializer
# --------------------
class ProfitLossReportSerializer(serializers.Serializer):
    total_sales = serializers.FloatField()
    total_purchase = serializers.FloatField()
    total_profit = serializers.FloatField()

class PurchaseReturnReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    supplier = serializers.CharField()
    total_amount = serializers.FloatField()
    return_amount = serializers.FloatField()
    date = serializers.DateField()



class TopSoldProductsSerializer(serializers.Serializer):
    product_name = serializers.CharField()  # match the key from values()
    quantity_sold = serializers.IntegerField()
    total_sales = serializers.FloatField()

class LowStockSerializer(serializers.Serializer):
    product = serializers.CharField()
    stock_qty = serializers.IntegerField()


class BadStockReportSerializer(serializers.Serializer):
    product = serializers.CharField()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()

class StockReportSerializer(serializers.Serializer):
    product = serializers.CharField()
    stock_qty = serializers.IntegerField()

class ExpenseReportView(APIView):
    def get(self, request):
        company_id = request.GET.get('company')  # optional filter by company
        start = request.GET.get('start')         # optional start date YYYY-MM-DD
        end = request.GET.get('end')             # optional end date YYYY-MM-DD

        expenses = Expense.objects.all()

        # Filter by company if provided
        if company_id:
            expenses = expenses.filter(company_id=company_id)

        # Filter by date range if both start and end are provided
        if start and end:
            expenses = expenses.filter(expense_date__range=[start, end])

        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)
