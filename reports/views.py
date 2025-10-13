from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum, F, FloatField
from django.utils.dateparse import parse_date

from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from returns.models import SalesReturn, PurchaseReturn, BadStock
from products.models import Product
from expenses.models import Expense

from .serializers import (
    SalesReportSerializer,
    PurchaseReportSerializer,
    ProfitLossReportSerializer,
    PurchaseReturnReportSerializer,
    TopSoldProductsSerializer,
    LowStockSerializer,
    BadStockReportSerializer,
    StockReportSerializer,
    ExpenseSerializer
)


# --------------------
# Sales Report
# --------------------

class SalesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        start = request.GET.get('start')
        end = request.GET.get('end')

        sales = Sale.objects.all()
       
        if start:
            start_date = parse_date(start)
            if start_date:
                sales = sales.filter(sale_date__date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                sales = sales.filter(sale_date__date__lte=end_date)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)
        start = request.GET.get('start')
        end = request.GET.get('end')

        purchases = Purchase.objects.all()
        
        if start:
            start_date = parse_date(start)
            if start_date:
                purchases = purchases.filter(date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                purchases = purchases.filter(date__lte=end_date)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)
        start = request.GET.get('start')
        end = request.GET.get('end')

        sales_items = SaleItem.objects.all()
        purchase_items = PurchaseItem.objects.all()
       
        if start:
            start_date = parse_date(start)
            if start_date:
                sales_items = sales_items.filter(sale__sale_date__date__gte=start_date)
                purchase_items = purchase_items.filter(purchase__date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                sales_items = sales_items.filter(sale__sale_date__date__lte=end_date)
                purchase_items = purchase_items.filter(purchase__date__lte=end_date)

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
# Expense Report
# --------------------
class ExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        start = request.GET.get('start')
        end = request.GET.get('end')

        expenses = Expense.objects.all()
       
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


# --------------------
# Purchase Return Report
# --------------------
class PurchaseReturnReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)
        start = request.GET.get('start')
        end = request.GET.get('end')

        returns = PurchaseReturn.objects.all()
      
        if start:
            start_date = parse_date(start)
            if start_date:
                returns = returns.filter(date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                returns = returns.filter(date__lte=end_date)

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)
        start = request.GET.get('start')
        end = request.GET.get('end')

        sales_returns = SalesReturn.objects.all()
        
        if start:
            start_date = parse_date(start)
            if start_date:
                sales_returns = sales_returns.filter(return_date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                sales_returns = sales_returns.filter(return_date__lte=end_date)

        report = []
        for sr in sales_returns:
            total_amount = sr.items.aggregate(
                total=Sum(F('quantity') * F('unit_price'), output_field=FloatField())
            )['total'] or 0
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)  # get the user's company from token
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)
        start = request.GET.get('start')
        end = request.GET.get('end')

        sale_items = SaleItem.objects.all()
        
        if start:
            start_date = parse_date(start)
            if start_date:
                sale_items = sale_items.filter(sale__sale_date__date__gte=start_date)
        if end:
            end_date = parse_date(end)
            if end_date:
                sale_items = sale_items.filter(sale__sale_date__date__lte=end_date)

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

        products_list = sorted(
            product_totals.values(),
            key=lambda x: x["quantity_sold"],
            reverse=True
        )

        serializer = TopSoldProductsSerializer(products_list, many=True)
        return Response(serializer.data)


# --------------------
# Low Stock Report
# --------------------
class LowStockReportView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bad_items = BadStock.objects.all()
        data = [{"product": b.product.name, "quantity": b.quantity, "reason": b.reason} for b in bad_items]
        serializer = BadStockReportSerializer(data, many=True)
        return Response(serializer.data)


# --------------------
# Stock Report
# --------------------
class StockReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = Product.objects.all()
        data = [{"product": p.name, "stock_qty": p.stock_qty} for p in products]
        serializer = StockReportSerializer(data, many=True)
        return Response(serializer.data)
