from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import datetime
from django.db.models import Sum, F, FloatField
from returns.models import SalesReturn, PurchaseReturn
from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from products.models import Product
from django.db.models import F, Sum, FloatField
from returns.models import BadStock # Assuming you have this model
from .serializers import (
    SalesReportSerializer, PurchaseReportSerializer, ProfitLossReportSerializer,
    PurchaseReturnReportSerializer, TopSoldProductsSerializer,
    LowStockSerializer, BadStockReportSerializer, StockReportSerializer
)
from decimal import Decimal

from returns.models import SalesReturn, SalesReturnItem
from expenses.models import Expense
from expenses.serializers import ExpenseSerializer
from django.utils.dateparse import parse_date
# --------------------
# Sales Report
# --------------------
class SalesReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        if not start_date or not end_date:
            return Response({"error": "Provide start and end dates"}, status=400)

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)

        sales = Sale.objects.filter(sale_date__date__range=[start, end])
        report = []
        for sale in sales:
            total_amount = sale.items.aggregate(
                total=Sum(F('quantity') * F('unit_price'), output_field=FloatField())
            )['total'] or 0
            total_discount = sale.items.aggregate(total=Sum('discount', output_field=FloatField()))['total'] or 0
            total_vat = sale.overall_vat_amount or 0
            net_amount = total_amount - total_discount + total_vat
            report.append({
                'invoice_no': sale.invoice_no,
                'customer': sale.customer.name if sale.customer else "Walk-in Customer",
                'total_amount': total_amount,
                'total_discount': total_discount,
                'total_vat': total_vat,
                'net_amount': net_amount,
                'date': sale.sale_date.date()
            })

        serializer = SalesReportSerializer(report, many=True)
        return Response(serializer.data)


# --------------------
# Purchase Report
# --------------------
class PurchaseReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        if not start_date or not end_date:
            return Response({"error": "Provide start and end dates"}, status=400)

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)

        purchases = Purchase.objects.filter(date__range=[start, end])
        report = []
        for purchase in purchases:
            total_amount = purchase.items.aggregate(
                total=Sum(F('qty') * F('price'), output_field=FloatField())
            )['total'] or 0
            total_discount = purchase.items.aggregate(total=Sum('discount', output_field=FloatField()))['total'] or 0
            net_amount = total_amount - total_discount
            report.append({
                'invoice_no': purchase.invoice_no,
                'supplier': purchase.supplier.name,
                'total_amount': total_amount,
                'total_discount': total_discount,
                'net_amount': net_amount,
                'date': purchase.date
            })

        serializer = PurchaseReportSerializer(report, many=True)
        return Response(serializer.data)


# --------------------
# Profit & Loss Report
# --------------------
class ProfitLossReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        if not start_date or not end_date:
            return Response({"error": "Provide start and end dates"}, status=400)

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)

        sales_items = SaleItem.objects.filter(sale__sale_date__date__range=[start, end])
        purchase_items = PurchaseItem.objects.filter(purchase__date__range=[start, end])

        total_sales = sum([item.quantity * item.unit_price for item in sales_items])
        total_purchase = sum([item.qty * item.price for item in purchase_items])
        total_profit = total_sales - total_purchase

        serializer = ProfitLossReportSerializer({
            'total_sales': total_sales,
            'total_purchase': total_purchase,
            'total_profit': total_profit
        })
        return Response(serializer.data)


# --------------------
# Purchase Return Report
# --------------------
class PurchaseReturnReportView(APIView):
    def get(self, request):
        start = datetime.strptime(request.GET.get('start'), "%Y-%m-%d").date()
        end = datetime.strptime(request.GET.get('end'), "%Y-%m-%d").date()
        returns = PurchaseReturn.objects.filter(date__range=[start, end])
        report = [{
            'invoice_no': r.purchase.invoice_no,
            'supplier': r.purchase.supplier.name,
            'total_amount': sum([i.subtotal() for i in r.items.all()]),
            'return_amount': r.return_amount,
            'date': r.date
        } for r in returns]
        serializer = PurchaseReturnReportSerializer(report, many=True)
        return Response(serializer.data)


# --------------------
# Sales Return Report
# --------------------


class SalesReturnReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        if not start_date or not end_date:
            return Response({"error": "Provide start and end dates"}, status=400)

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format, use YYYY-MM-DD"}, status=400)

        # Query SalesReturn using correct field
        sales_returns = SalesReturn.objects.filter(return_date__range=[start, end])

        report = []
        for sr in sales_returns:
            total_amount = sr.items.aggregate(
                total=Sum(F('quantity') * F('unit_price'), output_field=FloatField())
            )['total'] or 0

            # Convert to Decimal for safe arithmetic
            total_amount = Decimal(total_amount)
            discount = sr.discount or Decimal(0)
            vat = sr.vat or Decimal(0)
            service_charge = sr.service_charge or Decimal(0)
            delivery_charge = sr.delivery_charge or Decimal(0)

            report.append({
                'invoice_no': sr.invoice_no,
                'supplier': sr.account.name if sr.account else "Walk-in Customer",
                'total_amount': float(total_amount),
                'return_amount': float(total_amount - discount + vat + service_charge + delivery_charge),
                'date': sr.return_date
            })

        serializer = PurchaseReturnReportSerializer(report, many=True)
        return Response(serializer.data)

# --------------------
# Top Sold Products Report
# --------------------




class TopSoldProductsReportView(APIView):
    def get(self, request):
        start_str = request.GET.get('start')
        end_str = request.GET.get('end')

        if not start_str or not end_str:
            return Response({"error": "Please provide 'start' and 'end' query parameters"}, status=400)

        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Aggregate quantities and calculate total sales using your subtotal
        sale_items = SaleItem.objects.filter(
            sale__sale_date__date__range=[start, end]
        )

        # Dictionary to accumulate totals per product
        product_totals = {}
        for item in sale_items:
            pid = item.product.id
            if pid not in product_totals:
                product_totals[pid] = {
                    "product_name": item.product.name,
                    "quantity_sold": 0,
                    "total_sales": 0.0,
                }
            product_totals[pid]["quantity_sold"] += item.quantity
            product_totals[pid]["total_sales"] += float(item.subtotal())

        # Convert to list and sort by quantity_sold descending
        products_list = sorted(
            product_totals.values(),
            key=lambda x: x["quantity_sold"],
            reverse=True
        )

        serializer = TopSoldProductsSerializer(products_list, many=True)
        return Response(serializer.data)
# --------------------
# Low Stock Products Report
# --------------------
class LowStockReportView(APIView):
    def get(self, request):
        threshold = int(request.GET.get('threshold', 10))
        products = Product.objects.filter(stock_qty__lte=threshold)
        data = [{"product": p.name, "stock_qty": p.stock_qty} for p in products]
        serializer = LowStockSerializer(data, many=True)
        return Response(serializer.data)


# --------------------
# Bad Stock Report
# --------------------
class BadStockReportView(APIView):
    def get(self, request):
        bad_items = BadStock.objects.all()
        data = [{"product": b.product.name, "quantity": b.quantity, "reason": b.reason} for b in bad_items]
        serializer = BadStockReportSerializer(data, many=True)
        return Response(serializer.data)


# --------------------
# Stock Report
# --------------------
class StockReportView(APIView):
    def get(self, request):
        products = Product.objects.all()
        data = [{"product": p.name, "stock_qty": p.stock_qty} for p in products]
        serializer = StockReportSerializer(data, many=True)
        return Response(serializer.data)

class ExpenseReportView(APIView):
    def get(self, request):
        company_id = request.GET.get('company')
        start = request.GET.get('start')
        end = request.GET.get('end')

        expenses = Expense.objects.all()
        if company_id:
            expenses = expenses.filter(company_id=company_id)
        if start:
            start_date = parse_date(start)
            if start_date:
                expenses = expenses.filter(expense_date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                expenses = expenses.filter(expense_date__lte=end_date)

        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)