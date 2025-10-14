# reports/views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F, FloatField
from django.utils.dateparse import parse_date
from decimal import Decimal

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

# reports/utils.py
from rest_framework.response import Response

def custom_response(success=True, message="", data=None, status_code=200):
    """
    Standard response format for all APIs.

    :param success: bool, indicates success or failure
    :param message: str, human-readable message
    :param data: any, the response payload
    :param status_code: int, HTTP status code
    :return: DRF Response object
    """
    return Response({
        "status": success,
        "message": message,
        "data": data
    }, status=status_code)


def _parse_date_safe(date_str):
    """Returns a date or None (safe parse)."""
    if not date_str:
        return None
    return parse_date(date_str)


# --------------------
# Sales Report
# --------------------
class SalesReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            sales = Sale.objects.filter(company=company).order_by('sale_date')
            if start:
                sales = sales.filter(sale_date__date__gte=start)
            if end:
                sales = sales.filter(sale_date__date__lte=end)

            report = []
            for sale in sales:
                totals = sale.items.aggregate(
                    total_amount=Sum(F('quantity') * F('unit_price'), output_field=FloatField()),
                    total_discount=Sum('discount', output_field=FloatField())
                )
                total_amount = Decimal(totals.get('total_amount') or 0)
                total_discount = Decimal(totals.get('total_discount') or 0)
                total_vat = Decimal(sale.overall_vat_amount or 0)
                net_amount = total_amount - total_discount + total_vat

                report.append({
                    'invoice_no': sale.invoice_no,
                    'customer': sale.customer.name if getattr(sale, 'customer', None) else "Walk-in Customer",
                    'total_amount': float(total_amount),
                    'total_discount': float(total_discount),
                    'total_vat': float(total_vat),
                    'net_amount': float(net_amount),
                    'date': sale.sale_date.date() if getattr(sale, 'sale_date', None) else None
                })

            serializer = SalesReportSerializer(report, many=True)
            return custom_response(True, "Sales report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching sales report: {str(e)}", None, 500)


# --------------------
# Purchase Report
# --------------------
class PurchaseReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            purchases = Purchase.objects.filter(company=company).order_by('date')
            if start:
                purchases = purchases.filter(date__gte=start)
            if end:
                purchases = purchases.filter(date__lte=end)

            report = []
            for purchase in purchases:
                totals = purchase.items.aggregate(
                    total_amount=Sum(F('qty') * F('price'), output_field=FloatField()),
                    total_discount=Sum('discount', output_field=FloatField())
                )
                total_amount = Decimal(totals.get('total_amount') or 0)
                total_discount = Decimal(totals.get('total_discount') or 0)
                net_amount = total_amount - total_discount

                report.append({
                    'invoice_no': purchase.invoice_no,
                    'supplier': getattr(purchase.supplier, 'name', None),
                    'total_amount': float(total_amount),
                    'total_discount': float(total_discount),
                    'net_amount': float(net_amount),
                    'date': purchase.date
                })

            serializer = PurchaseReportSerializer(report, many=True)
            return custom_response(True, "Purchase report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching purchase report: {str(e)}", None, 500)


# --------------------
# Profit & Loss Report
# --------------------
class ProfitLossReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            sales_items = SaleItem.objects.filter(sale__company=company)
            purchase_items = PurchaseItem.objects.filter(purchase__company=company)

            if start:
                sales_items = sales_items.filter(sale__sale_date__date__gte=start)
                purchase_items = purchase_items.filter(purchase__date__gte=start)
            if end:
                sales_items = sales_items.filter(sale__sale_date__date__lte=end)
                purchase_items = purchase_items.filter(purchase__date__lte=end)

            sales_agg = sales_items.aggregate(total_sales=Sum(F('quantity') * F('unit_price'), output_field=FloatField()))
            purchase_agg = purchase_items.aggregate(total_purchase=Sum(F('qty') * F('price'), output_field=FloatField()))

            total_sales = Decimal(sales_agg.get('total_sales') or 0)
            total_purchase = Decimal(purchase_agg.get('total_purchase') or 0)
            total_profit = total_sales - total_purchase

            serializer = ProfitLossReportSerializer({
                'total_sales': float(total_sales),
                'total_purchase': float(total_purchase),
                'total_profit': float(total_profit)
            })
            return custom_response(True, "Profit & Loss report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching profit & loss report: {str(e)}", None, 500)


# --------------------
# Expense Report
# --------------------
class ExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            expenses = Expense.objects.filter(company=company).order_by('expense_date')
            if start:
                expenses = expenses.filter(expense_date__gte=start)
            if end:
                expenses = expenses.filter(expense_date__lte=end)

            serializer = ExpenseSerializer(expenses, many=True)
            return custom_response(True, "Expense report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching expense report: {str(e)}", None, 500)


# --------------------
# Purchase Return Report
# --------------------
class PurchaseReturnReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            returns = PurchaseReturn.objects.filter(company=company).order_by('date')
            if start:
                returns = returns.filter(date__gte=start)
            if end:
                returns = returns.filter(date__lte=end)

            report = [{
                'invoice_no': r.purchase.invoice_no if getattr(r, 'purchase', None) else None,
                'supplier': getattr(r.purchase.supplier, 'name', None) if getattr(r, 'purchase', None) else None,
                'total_amount': float(sum([i.subtotal() for i in r.items.all()] or [0])),
                'return_amount': float(r.return_amount or 0),
                'date': r.date
            } for r in returns]

            serializer = PurchaseReturnReportSerializer(report, many=True)
            return custom_response(True, "Purchase return report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching purchase return report: {str(e)}", None, 500)


# --------------------
# Sales Return Report
# --------------------
class SalesReturnReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            sales_returns = SalesReturn.objects.filter(company=company).order_by('return_date')
            if start:
                sales_returns = sales_returns.filter(return_date__gte=start)
            if end:
                sales_returns = sales_returns.filter(return_date__lte=end)

            report = []
            for sr in sales_returns:
                totals = sr.items.aggregate(total=Sum(F('quantity') * F('unit_price'), output_field=FloatField()))
                total_amount = Decimal(totals.get('total') or 0)
                discount = Decimal(sr.discount or 0)
                vat = Decimal(sr.vat or 0)
                service_charge = Decimal(sr.service_charge or 0)
                delivery_charge = Decimal(sr.delivery_charge or 0)

                return_amount = total_amount - discount + vat + service_charge + delivery_charge

                report.append({
                    'invoice_no': sr.invoice_no,
                    'supplier': sr.account.name if getattr(sr, 'account', None) else "Walk-in Customer",
                    'total_amount': float(total_amount),
                    'return_amount': float(return_amount),
                    'date': sr.return_date
                })

            serializer = PurchaseReturnReportSerializer(report, many=True)
            return custom_response(True, "Sales return report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching sales return report: {str(e)}", None, 500)


# --------------------
# Top Sold Products Report
# --------------------
class TopSoldProductsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            start = _parse_date_safe(request.GET.get('start'))
            end = _parse_date_safe(request.GET.get('end'))

            sale_items = SaleItem.objects.filter(sale__company=company)
            if start:
                sale_items = sale_items.filter(sale__sale_date__date__gte=start)
            if end:
                sale_items = sale_items.filter(sale__sale_date__date__lte=end)

            product_totals = {}
            for item in sale_items.select_related('product'):
                product = getattr(item, 'product', None)
                if not product:
                    continue
                pid = product.id
                product_totals.setdefault(pid, {
                    "product_id": pid,
                    "product_name": product.name,
                    "quantity_sold": 0,
                    "total_sales": 0.0,
                })
                product_totals[pid]["quantity_sold"] += item.quantity or 0
                product_totals[pid]["total_sales"] += float(item.subtotal() or 0)

            products_list = sorted(product_totals.values(), key=lambda x: x["quantity_sold"], reverse=True)
            serializer = TopSoldProductsSerializer(products_list, many=True)
            return custom_response(True, "Top sold products report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching top sold products report: {str(e)}", None, 500)


# --------------------
# Low Stock Report
# --------------------
class LowStockReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            threshold = int(request.GET.get('threshold', 10))
            products = Product.objects.filter(company=company, stock_qty__lte=threshold).order_by('stock_qty')
            data = [{"product": p.name, "stock_qty": p.stock_qty} for p in products]
            serializer = LowStockSerializer(data, many=True)
            return custom_response(True, "Low stock report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching low stock report: {str(e)}", None, 500)


# --------------------
# Bad Stock Report
# --------------------
class BadStockReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            bad_items = BadStock.objects.filter(company=company).select_related('product')
            data = [{"product": b.product.name, "quantity": b.quantity, "reason": b.reason} for b in bad_items]
            serializer = BadStockReportSerializer(data, many=True)
            return custom_response(True, "Bad stock report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching bad stock report: {str(e)}", None, 500)


# --------------------
# Stock Report
# --------------------
class StockReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company", None, 400)

            products = Product.objects.filter(company=company)
            data = [{"product": p.name, "stock_qty": p.stock_qty} for p in products]
            serializer = StockReportSerializer(data, many=True)
            return custom_response(True, "Stock report fetched successfully", serializer.data)
        except Exception as e:
            return custom_response(False, f"Error fetching stock report: {str(e)}", None, 500)
