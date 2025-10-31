# reports/views.py - COMPLETE UPDATED VERSION
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F, FloatField, Count, Q, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from decimal import Decimal
from django.utils import timezone

from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from returns.models import SalesReturn, PurchaseReturn, BadStock
from products.models import Product
from expenses.models import Expense
from core.base_viewsets import BaseReportView
from .utils import custom_response, build_summary, build_advanced_summary
from .serializers import (
    SalesReportSerializer, SalesReportFilterSerializer,
    PurchaseReportSerializer, PurchaseReportFilterSerializer,
    ProfitLossReportSerializer, ExpenseFilterSerializer,
    PurchaseReturnReportSerializer, SalesReturnReportSerializer,
    TopSoldProductsSerializer, LowStockSerializer, StockFilterSerializer,
    BadStockReportSerializer, StockReportSerializer, ExpenseSerializer,
    ReportSummarySerializer, CustomerDueAdvanceSerializer,  
    SupplierDueAdvanceSerializer, 
    CustomerLedgerSerializer, SupplierLedgerSerializer,
    CustomerLedgerFilterSerializer, SupplierLedgerFilterSerializer,
    SupplierDueAdvanceFilterSerializer, CustomerDueAdvanceFilterSerializer
)

# --------------------
# Sales Report - Updated Format
# --------------------
class SalesReportView(BaseReportView):
    filter_serializer_class = SalesReportFilterSerializer
    cache_timeout = 600

    @method_decorator(cache_page(600))
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            sales = Sale.objects.filter(company=company).select_related(
                'customer', 'sale_by'
            ).prefetch_related(
                'items', 'items__product'
            ).order_by('-sale_date')
            
            if start and end:
                sales = sales.filter(sale_date__date__range=[start, end])
            
            filter_q = Q()
            if filters.get('customer'):
                filter_q &= Q(customer_id=filters['customer'])
            if filters.get('payment_status'):
                filter_q &= Q(payment_status=filters['payment_status'])
            if filters.get('sale_type'):
                filter_q &= Q(sale_type=filters['sale_type'])
            if filters.get('invoice_no'):
                filter_q &= Q(invoice_no__icontains=filters['invoice_no'])
            
            sales = sales.filter(filter_q)

            report_data = []
            sl_number = 1
            
            for sale in sales:
                sales_price = 0.0
                cost_price = 0.0
                
                for item in sale.items.all():
                    item_sales_price = (item.quantity or 0) * (item.unit_price or 0)
                    sales_price += float(item_sales_price)
                    
                    if hasattr(item, 'product') and item.product:
                        item_cost_price = (item.quantity or 0) * (item.product.purchase_price or 0)
                        cost_price += float(item_cost_price)
                
                profit = sales_price - cost_price
                collect_amount = float(sale.paid_amount or 0)
                due_amount = float(sale.due_amount or 0)
                
                sales_by = ""
                if sale.sale_by:
                    sales_by = sale.sale_by.get_full_name() or sale.sale_by.username
                else:
                    sales_by = "Unknown"
                
                net_amount = sales_price
                if filters.get('min_amount') and net_amount < float(filters['min_amount']):
                    continue
                if filters.get('max_amount') and net_amount > float(filters['max_amount']):
                    continue
                
                report_data.append({
                    'sl': sl_number,
                    'invoice_no': sale.invoice_no,
                    'sale_date': sale.sale_date.date() if sale.sale_date else None,
                    'customer_name': sale.customer.name if sale.customer else "Walk-in Customer",
                    'sales_by': sales_by,
                    'sales_price': round(sales_price, 2),
                    'cost_price': round(cost_price, 2),
                    'profit': round(profit, 2),
                    'collect_amount': round(collect_amount, 2),
                    'due_amount': round(due_amount, 2),
                    'customer_id': sale.customer.id if sale.customer else None,
                    'payment_status': getattr(sale, 'payment_status', 'unknown'),
                    'sale_type': getattr(sale, 'sale_type', 'retail')
                })
                sl_number += 1
            
            serializer = SalesReportSerializer(report_data, many=True)
            summary = self._build_sales_summary(report_data, (start, end))
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': summary,
                'filters_applied': {
                    'date_range': f"{start} to {end}" if start and end else "Not specified",
                    **{k: v for k, v in filters.items() if v is not None}
                }
            }
            
            return custom_response(True, "Sales report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _build_sales_summary(self, report_data, date_range):
        if not report_data:
            return {
                'total_sales': 0, 'total_cost': 0, 'total_profit': 0,
                'total_collected': 0, 'total_due': 0, 'average_profit_margin': 0,
                'date_range': {
                    'start': date_range[0].isoformat() if date_range[0] else None,
                    'end': date_range[1].isoformat() if date_range[1] else None
                }
            }
        
        total_sales = sum(item['sales_price'] for item in report_data)
        total_cost = sum(item['cost_price'] for item in report_data)
        total_profit = sum(item['profit'] for item in report_data)
        total_collected = sum(item['collect_amount'] for item in report_data)
        total_due = sum(item['due_amount'] for item in report_data)
        
        average_profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        
        return {
            'total_sales': round(total_sales, 2),
            'total_cost': round(total_cost, 2),
            'total_profit': round(total_profit, 2),
            'total_collected': round(total_collected, 2),
            'total_due': round(total_due, 2),
            'average_profit_margin': round(average_profit_margin, 2),
            'total_transactions': len(report_data),
            'date_range': {
                'start': date_range[0].isoformat() if date_range[0] else None,
                'end': date_range[1].isoformat() if date_range[1] else None
            }
        }

# --------------------
# Purchase Report - Updated Format
# --------------------
class PurchaseReportView(BaseReportView):
    filter_serializer_class = PurchaseReportFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            purchases = Purchase.objects.filter(company=company).select_related(
                'supplier'
            ).prefetch_related(
                'items'
            ).order_by('-purchase_date')
            
            if start and end:
                purchases = purchases.filter(purchase_date__range=[start, end])
            
            filter_q = Q()
            if filters.get('supplier'):
                filter_q &= Q(supplier_id=filters['supplier'])
            if filters.get('status'):
                filter_q &= Q(status=filters['status'])
            if filters.get('payment_status'):
                filter_q &= Q(payment_status=filters['payment_status'])
            if filters.get('invoice_no'):
                filter_q &= Q(invoice_no__icontains=filters['invoice_no'])
            
            purchases = purchases.filter(filter_q)
            
            report_data = []
            sl_number = 1
            
            for purchase in purchases:
                net_total = float(purchase.grand_total or 0)
                paid_total = float(purchase.paid_amount or 0)
                due_total = float(purchase.due_amount or 0)
                
                if filters.get('min_amount') and net_total < float(filters['min_amount']):
                    continue
                if filters.get('max_amount') and net_total > float(filters['max_amount']):
                    continue
                
                report_data.append({
                    'sl': sl_number,
                    'invoice_no': purchase.invoice_no,
                    'purchase_date': purchase.purchase_date,
                    'supplier': purchase.supplier.name if purchase.supplier else 'N/A',
                    'net_total': round(net_total, 2),
                    'paid_total': round(paid_total, 2),
                    'due_total': round(due_total, 2),
                    'supplier_id': purchase.supplier.id if purchase.supplier else None,
                    'status': getattr(purchase, 'status', 'completed'),
                    'payment_status': purchase.payment_status,
                    'location': getattr(purchase, 'location', 'N/A')
                })
                sl_number += 1
            
            serializer = PurchaseReportSerializer(report_data, many=True)
            summary = self._build_purchase_summary(report_data, (start, end))
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': summary,
                'filters_applied': {
                    'date_range': f"{start} to {end}" if start and end else "Not specified",
                    **{k: v for k, v in filters.items() if v is not None}
                }
            }
            
            return custom_response(True, "Purchase report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _build_purchase_summary(self, report_data, date_range):
        if not report_data:
            return {
                'total_purchases': 0, 'total_paid': 0, 'total_due': 0,
                'date_range': {
                    'start': date_range[0].isoformat() if date_range[0] else None,
                    'end': date_range[1].isoformat() if date_range[1] else None
                }
            }
        
        total_purchases = sum(item['net_total'] for item in report_data)
        total_paid = sum(item['paid_total'] for item in report_data)
        total_due = sum(item['due_total'] for item in report_data)
        
        return {
            'total_purchases': round(total_purchases, 2),
            'total_paid': round(total_paid, 2),
            'total_due': round(total_due, 2),
            'total_transactions': len(report_data),
            'date_range': {
                'start': date_range[0].isoformat() if date_range[0] else None,
                'end': date_range[1].isoformat() if date_range[1] else None
            }
        }

# --------------------
# Low Stock Products Report - Updated Format
# --------------------
class LowStockReportView(BaseReportView):
    filter_serializer_class = StockFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            
            threshold = filters.get('threshold', 10)
            
            products = Product.objects.filter(
                company=company, 
                stock_qty__lte=threshold
            ).select_related('category', 'brand')
            
            if filters.get('category'):
                products = products.filter(category_id=filters['category'])
                
            products_with_sales = []
            for product in products:
                total_sold = SaleItem.objects.filter(
                    product=product,
                    sale__company=company
                ).aggregate(total_sold=Sum('quantity'))['total_sold'] or 0
                
                products_with_sales.append({
                    'product': product,
                    'total_sold': total_sold
                })
            
            products_with_sales.sort(key=lambda x: x['product'].stock_qty)
            
            report_data = []
            sl_number = 1
            
            for item in products_with_sales:
                product = item['product']
                report_data.append({
                    'sl': sl_number,
                    'product_name': product.name,
                    'selling_price': float(product.selling_price or 0),
                    'alert_quantity': product.alert_quantity,
                    'total_stock_quantity': product.stock_qty,
                    'total_sold_quantity': item['total_sold'],
                    'product_id': product.id,
                    'category': product.category.name if product.category else 'N/A',
                    'brand': product.brand.name if product.brand else 'N/A'
                })
                sl_number += 1
            
            serializer = LowStockSerializer(report_data, many=True)
            
            response_data = {
                'report': serializer.data,
                'summary': {
                    'total_low_stock_items': len(report_data),
                    'threshold': threshold,
                    'critical_items': len([p for p in report_data if p['total_stock_quantity'] == 0])
                }
            }
            
            return custom_response(True, "Low stock report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Top Sold Products Report - Updated Format
# --------------------
class TopSoldProductsReportView(BaseReportView):
    @method_decorator(cache_page(600))
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            sale_items = SaleItem.objects.filter(
                sale__company=company
            ).select_related('product')
            
            if start and end:
                sale_items = sale_items.filter(sale__sale_date__date__range=[start, end])
            
            category_id = request.GET.get('category')
            if category_id:
                sale_items = sale_items.filter(product__category_id=category_id)
            
            limit = int(request.GET.get('limit', 10))
            
            product_totals = sale_items.values(
                'product__id', 'product__name', 'product__selling_price'
            ).annotate(
                quantity_sold=Sum('quantity'),
                total_sales=Sum(F('quantity') * F('unit_price'), output_field=FloatField())
            ).order_by('-quantity_sold')[:limit]
            
            report_data = []
            sl_number = 1
            
            for item in product_totals:
                report_data.append({
                    'sl': sl_number,
                    'product_name': item['product__name'],
                    'selling_price': float(item['product__selling_price'] or 0),
                    'total_sold_quantity': item['quantity_sold'] or 0,
                    'total_sold_price': float(item['total_sales'] or 0),
                    'product_id': item['product__id']
                })
                sl_number += 1
            
            serializer = TopSoldProductsSerializer(report_data, many=True)
            
            response_data = {
                'report': serializer.data,
                'summary': {
                    'total_products': len(report_data),
                    'total_quantity_sold': sum(item['total_sold_quantity'] for item in report_data),
                    'total_sales': sum(item['total_sold_price'] for item in report_data),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Top sold products report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Supplier Due & Advance Report - Updated Format
# --------------------
class SupplierDueAdvanceReportView(BaseReportView):
    filter_serializer_class = SupplierDueAdvanceFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            from suppliers.models import Supplier
            suppliers = Supplier.objects.filter(company=company, is_active=True)
            
            if filters.get('supplier'):
                suppliers = suppliers.filter(id=filters['supplier'])
            
            report_data = []
            sl_number = 1
            
            for supplier in suppliers:
                purchases = Purchase.objects.filter(
                    company=company, 
                    supplier=supplier
                )
                
                if start and end:
                    purchases = purchases.filter(purchase_date__range=[start, end])
                
                purchase_totals = purchases.aggregate(
                    total_purchase=Sum('grand_total'),
                    total_paid=Sum('paid_amount'),
                    count=Count('id')
                )
                
                total_purchase = float(purchase_totals['total_purchase'] or 0)
                total_paid = float(purchase_totals['total_paid'] or 0)
                present_due = max(0, total_purchase - total_paid)
                present_advance = max(0, total_paid - total_purchase)
                
                if filters.get('status') != 'all':
                    if filters['status'] == 'due' and present_due <= 0:
                        continue
                    elif filters['status'] == 'advance' and present_advance <= 0:
                        continue
                
                if total_purchase > 0 or filters.get('status') != 'all':
                    report_data.append({
                        'sl': sl_number,
                        'supplier_no': supplier.id,
                        'supplier_name': supplier.name,
                        'phone': supplier.phone or 'N/A',
                        'email': supplier.email or 'N/A',
                        'present_due': round(present_due, 2),
                        'present_advance': round(present_advance, 2),
                        'supplier_id': supplier.id
                    })
                    sl_number += 1
            
            report_data.sort(key=lambda x: x['present_due'] or x['present_advance'], reverse=True)
            
            serializer = SupplierDueAdvanceSerializer(report_data, many=True)
            
            total_suppliers = len(report_data)
            total_overall_due = sum(item['present_due'] for item in report_data)
            total_overall_advance = sum(item['present_advance'] for item in report_data)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_suppliers': total_suppliers,
                    'total_due_amount': round(total_overall_due, 2),
                    'total_advance_amount': round(total_overall_advance, 2),
                    'net_balance': round(total_overall_advance - total_overall_due, 2),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Supplier due & advance report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Supplier Ledger Details - Updated Format
# --------------------
class SupplierLedgerReportView(BaseReportView):
    filter_serializer_class = SupplierLedgerFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            if not filters.get('supplier'):
                return custom_response(False, "Supplier ID is required for ledger report", None, 400)
            
            from suppliers.models import Supplier
            try:
                supplier = Supplier.objects.get(id=filters['supplier'], company=company)
            except Supplier.DoesNotExist:
                return custom_response(False, "Supplier not found", None, 404)
            
            ledger_entries = []
            running_balance = 0
            sl_number = 1
            
            # 1. Purchase transactions
            if filters.get('transaction_type') in ['all', 'purchase']:
                purchases = Purchase.objects.filter(
                    company=company, 
                    supplier=supplier
                )
                
                if start and end:
                    purchases = purchases.filter(purchase_date__range=[start, end])
                
                for purchase in purchases.order_by('purchase_date'):
                    running_balance += float(purchase.grand_total)
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': purchase.invoice_no,
                        'date': purchase.purchase_date,
                        'particular': 'Purchase',
                        'details': f'Purchase - {purchase.invoice_no}',
                        'type': 'Purchase',
                        'method': purchase.payment_method or 'N/A',
                        'debit': round(float(purchase.grand_total), 2),
                        'credit': 0.0,
                        'due': round(running_balance, 2),
                        'supplier_id': supplier.id,
                        'supplier_name': supplier.name
                    })
                    sl_number += 1
            
            # 2. Payment transactions
            if filters.get('transaction_type') in ['all', 'payment']:
                try:
                    from suppliers.models import SupplierPayment
                    payments = SupplierPayment.objects.filter(
                        company=company,
                        supplier=supplier
                    )
                    
                    if start and end:
                        payments = payments.filter(payment_date__range=[start, end])
                    
                    for payment in payments.order_by('payment_date'):
                        running_balance -= float(payment.amount)
                        
                        ledger_entries.append({
                            'sl': sl_number,
                            'voucher_no': payment.payment_number or f"PYMT-{payment.id}",
                            'date': payment.payment_date,
                            'particular': 'Payment',
                            'details': f'Payment - {payment.payment_method}',
                            'type': 'Payment',
                            'method': payment.payment_method or 'N/A',
                            'debit': 0.0,
                            'credit': round(float(payment.amount), 2),
                            'due': round(running_balance, 2),
                            'supplier_id': supplier.id,
                            'supplier_name': supplier.name
                        })
                        sl_number += 1
                except ImportError:
                    pass
            
            # 3. Purchase Return transactions
            if filters.get('transaction_type') in ['all', 'return']:
                purchase_returns = PurchaseReturn.objects.filter(company=company)
                
                if hasattr(PurchaseReturn, 'purchase_ref'):
                    purchase_returns = purchase_returns.filter(purchase_ref__supplier=supplier)
                elif hasattr(PurchaseReturn, 'purchase'):
                    purchase_returns = purchase_returns.filter(purchase__supplier=supplier)
                
                if start and end:
                    purchase_returns = purchase_returns.filter(date__range=[start, end])
                
                for return_obj in purchase_returns.order_by('date'):
                    return_amount = 0
                    if hasattr(return_obj, 'items'):
                        for item in return_obj.items.all():
                            if hasattr(item, 'subtotal'):
                                return_amount += float(item.subtotal())
                    
                    running_balance -= return_amount
                    
                    reference_no = "RET-UNKNOWN"
                    if hasattr(return_obj, 'purchase_ref') and return_obj.purchase_ref:
                        reference_no = f"RET-{return_obj.purchase_ref.invoice_no}"
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': reference_no,
                        'date': return_obj.date,
                        'particular': 'Return',
                        'details': 'Purchase Return',
                        'type': 'Return',
                        'method': 'N/A',
                        'debit': 0.0,
                        'credit': round(return_amount, 2),
                        'due': round(running_balance, 2),
                        'supplier_id': supplier.id,
                        'supplier_name': supplier.name
                    })
                    sl_number += 1
            
            # Sort all entries by date
            ledger_entries.sort(key=lambda x: x['date'])
            
            # Re-number SL after sorting
            for i, entry in enumerate(ledger_entries, 1):
                entry['sl'] = i
            
            serializer = SupplierLedgerSerializer(ledger_entries, many=True)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.name,
                    'closing_balance': round(running_balance, 2),
                    'total_transactions': len(ledger_entries),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Supplier ledger report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Customer Due & Advance Report - Updated Format
# --------------------
class CustomerDueAdvanceReportView(BaseReportView):
    filter_serializer_class = CustomerDueAdvanceFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            from customers.models import Customer
            customers = Customer.objects.filter(company=company, is_active=True)
            
            if filters.get('customer'):
                customers = customers.filter(id=filters['customer'])
            
            report_data = []
            sl_number = 1
            
            for customer in customers:
                sales = Sale.objects.filter(
                    company=company, 
                    customer=customer
                )
                
                if start and end:
                    sales = sales.filter(sale_date__date__range=[start, end])
                
                sales_totals = sales.aggregate(
                    total_sales=Sum('grand_total'),
                    total_received=Sum('paid_amount'),
                    count=Count('id')
                )
                
                total_sales = float(sales_totals['total_sales'] or 0)
                total_received = float(sales_totals['total_received'] or 0)
                present_due = max(0, total_sales - total_received)
                present_advance = max(0, total_received - total_sales)
                
                if filters.get('status') != 'all':
                    if filters['status'] == 'due' and present_due <= 0:
                        continue
                    elif filters['status'] == 'advance' and present_advance <= 0:
                        continue
                
                if total_sales > 0 or filters.get('status') != 'all':
                    report_data.append({
                        'sl': sl_number,
                        'customer_no': customer.id,
                        'customer_name': customer.name,
                        'phone': customer.phone or 'N/A',
                        'email': customer.email or 'N/A',
                        'present_due': round(present_due, 2),
                        'present_advance': round(present_advance, 2),
                        'customer_id': customer.id
                    })
                    sl_number += 1
            
            report_data.sort(key=lambda x: x['present_due'] or x['present_advance'], reverse=True)
            
            serializer = CustomerDueAdvanceSerializer(report_data, many=True)
            
            total_customers = len(report_data)
            total_overall_due = sum(item['present_due'] for item in report_data)
            total_overall_advance = sum(item['present_advance'] for item in report_data)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_customers': total_customers,
                    'total_due_amount': round(total_overall_due, 2),
                    'total_advance_amount': round(total_overall_advance, 2),
                    'net_balance': round(total_overall_advance - total_overall_due, 2),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Customer due & advance report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Customer Ledger Details - Updated Format
# --------------------
class CustomerLedgerReportView(BaseReportView):
    filter_serializer_class = CustomerLedgerFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            if not filters.get('customer'):
                return custom_response(False, "Customer ID is required for ledger report", None, 400)
            
            from customers.models import Customer
            try:
                customer = Customer.objects.get(id=filters['customer'], company=company)
            except Customer.DoesNotExist:
                return custom_response(False, "Customer not found", None, 404)
            
            ledger_entries = []
            running_balance = 0
            sl_number = 1
            
            # 1. Sale transactions
            if filters.get('transaction_type') in ['all', 'sale']:
                sales = Sale.objects.filter(
                    company=company, 
                    customer=customer
                )
                
                if start and end:
                    sales = sales.filter(sale_date__date__range=[start, end])
                
                for sale in sales.order_by('sale_date'):
                    running_balance += float(sale.grand_total)
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': sale.invoice_no,
                        'date': sale.sale_date.date(),
                        'particular': 'Sale',
                        'details': f'Sale - {sale.invoice_no}',
                        'type': 'Sale',
                        'method': sale.payment_method or 'N/A',
                        'debit': round(float(sale.grand_total), 2),
                        'credit': 0.0,
                        'due': round(running_balance, 2),
                        'customer_id': customer.id,
                        'customer_name': customer.name
                    })
                    sl_number += 1
            
            # 2. Payment transactions
            if filters.get('transaction_type') in ['all', 'payment']:
                try:
                    from money_receipts.models import MoneyReceipt
                    payments = MoneyReceipt.objects.filter(
                        company=company,
                        customer=customer
                    )
                    
                    if start and end:
                        payments = payments.filter(payment_date__date__range=[start, end])
                    
                    for payment in payments.order_by('payment_date'):
                        running_balance -= float(payment.amount)
                        
                        ledger_entries.append({
                            'sl': sl_number,
                            'voucher_no': payment.mr_no,
                            'date': payment.payment_date.date(),
                            'particular': 'Payment',
                            'details': f'Payment - {payment.payment_method}',
                            'type': 'Payment',
                            'method': payment.payment_method or 'N/A',
                            'debit': 0.0,
                            'credit': round(float(payment.amount), 2),
                            'due': round(running_balance, 2),
                            'customer_id': customer.id,
                            'customer_name': customer.name
                        })
                        sl_number += 1
                except ImportError:
                    pass
            
            # 3. Sales Return transactions
            if filters.get('transaction_type') in ['all', 'return']:
                sales_returns = SalesReturn.objects.filter(company=company)
                
                if hasattr(SalesReturn, 'customer'):
                    sales_returns = sales_returns.filter(customer=customer)
                elif hasattr(SalesReturn, 'sale__customer'):
                    sales_returns = sales_returns.filter(sale__customer=customer)
                
                if start and end:
                    sales_returns = sales_returns.filter(return_date__range=[start, end])
                
                for return_obj in sales_returns.order_by('return_date'):
                    return_amount = 0
                    for item in return_obj.items.all():
                        item_total = (item.quantity or 0) * (item.unit_price or 0)
                        return_amount += float(item_total)
                    
                    running_balance -= return_amount
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': getattr(return_obj, 'invoice_no', f"RET-{return_obj.id}"),
                        'date': return_obj.return_date,
                        'particular': 'Return',
                        'details': 'Sales Return',
                        'type': 'Return',
                        'method': 'N/A',
                        'debit': 0.0,
                        'credit': round(return_amount, 2),
                        'due': round(running_balance, 2),
                        'customer_id': customer.id,
                        'customer_name': customer.name
                    })
                    sl_number += 1
            
            # Sort all entries by date
            ledger_entries.sort(key=lambda x: x['date'])
            
            # Re-number SL after sorting
            for i, entry in enumerate(ledger_entries, 1):
                entry['sl'] = i
            
            serializer = CustomerLedgerSerializer(ledger_entries, many=True)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'closing_balance': round(running_balance, 2),
                    'total_transactions': len(ledger_entries),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Customer ledger report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Stock Report - Updated Format
# --------------------
class StockReportView(BaseReportView):
    filter_serializer_class = StockFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            
            products = Product.objects.filter(company=company).select_related('category', 'brand')
            
            if filters.get('category'):
                products = products.filter(category_id=filters['category'])
            if filters.get('min_stock'):
                products = products.filter(stock_qty__gte=filters['min_stock'])
            if filters.get('max_stock'):
                products = products.filter(stock_qty__lte=filters['max_stock'])
                
            products = products.order_by('name')
            
            report_data = []
            sl_number = 1
            
            for product in products:
                # Calculate average purchase price from purchase items
                avg_purchase_price = PurchaseItem.objects.filter(
                    product=product,
                    purchase__company=company
                ).aggregate(avg_price=Avg('price'))['avg_price'] or product.purchase_price
                
                # Calculate stock value
                stock_value = product.stock_qty * (product.purchase_price or 0)
                
                report_data.append({
                    'sl': sl_number,
                    'product_no': product.id,
                    'product_name': product.name,
                    'category': product.category.name if product.category else 'N/A',
                    'brand': product.brand.name if product.brand else 'N/A',
                    'avg_purchase_price': round(float(avg_purchase_price), 2),
                    'selling_price': round(float(product.selling_price or 0), 2),
                    'current_stock': product.stock_qty,
                    'value': round(stock_value, 2),
                    'product_id': product.id
                })
                sl_number += 1
            
            serializer = StockReportSerializer(report_data, many=True)
            
            total_stock_value = sum(item['value'] for item in report_data)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_products': len(report_data),
                    'total_stock_value': round(total_stock_value, 2),
                    'total_stock_quantity': sum(item['current_stock'] for item in report_data)
                }
            }
            
            return custom_response(True, "Stock report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

# --------------------
# Keep existing reports (ProfitLoss, Expense, Returns, etc.) with SL numbers
# --------------------
class ProfitLossReportView(BaseReportView):
    @method_decorator(cache_page(300))
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            # Sales data
            sales_query = Sale.objects.filter(company=company)
            if start and end:
                sales_query = sales_query.filter(sale_date__date__range=[start, end])
            
            sales_data = sales_query.aggregate(
                total_sales=Sum('grand_total'),
                total_sales_count=Count('id')
            )
            
            # Purchase data
            purchase_query = Purchase.objects.filter(company=company)
            if start and end:
                purchase_query = purchase_query.filter(purchase_date__range=[start, end])
            
            purchase_data = purchase_query.aggregate(
                total_purchase=Sum('grand_total'),
                total_purchase_count=Count('id')
            )
            
            # Expense data
            expenses = Expense.objects.filter(company=company)
            if start and end:
                expenses = expenses.filter(expense_date__range=[start, end])
            
            expense_data = expenses.aggregate(
                total_expenses=Sum('amount'),
                expense_count=Count('id')
            )
            
            # Return data
            sales_return_query = SalesReturn.objects.filter(company=company)
            purchase_return_query = PurchaseReturn.objects.filter(company=company)
            
            if start and end:
                sales_return_query = sales_return_query.filter(return_date__range=[start, end])
                purchase_return_query = purchase_return_query.filter(date__range=[start, end])
            
            # Calculate sales return total
            sales_return_total = 0
            for sales_return in sales_return_query:
                items_total = sum([
                    (item.quantity or 0) * (item.unit_price or 0) 
                    for item in sales_return.items.all()
                ])
                discount = float(getattr(sales_return, 'discount', 0) or 0)
                vat = float(getattr(sales_return, 'vat', 0) or 0)
                service_charge = float(getattr(sales_return, 'service_charge', 0) or 0)
                delivery_charge = float(getattr(sales_return, 'delivery_charge', 0) or 0)
                
                return_amount = items_total - discount + vat + service_charge + delivery_charge
                sales_return_total += return_amount
            
            # Calculate purchase return total
            purchase_return_total = 0
            for purchase_return in purchase_return_query:
                if hasattr(purchase_return, 'return_amount') and purchase_return.return_amount:
                    purchase_return_total += float(purchase_return.return_amount)
                else:
                    items_total = 0
                    if hasattr(purchase_return, 'items'):
                        for item in purchase_return.items.all():
                            if hasattr(item, 'subtotal'):
                                items_total += float(item.subtotal())
                    purchase_return_total += items_total
            
            # Calculations
            total_sales = sales_data['total_sales'] or 0
            total_purchase = purchase_data['total_purchase'] or 0
            total_expenses = expense_data['total_expenses'] or 0
            
            gross_profit = Decimal(total_sales) - Decimal(total_purchase)
            net_profit = gross_profit - Decimal(total_expenses) + Decimal(purchase_return_total) - Decimal(sales_return_total)
            
            # Category breakdown
            expense_by_category = expenses.values(
                'head__name', 'subhead__name'
            ).annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            category_breakdown = []
            for item in expense_by_category:
                category_breakdown.append({
                    'head': item['head__name'],
                    'subhead': item['subhead__name'] or 'No Subcategory',
                    'total': float(item['total'])
                })
            
            data = {
                'total_sales': float(total_sales),
                'total_purchase': float(total_purchase),
                'total_expenses': float(total_expenses),
                'sales_returns': float(sales_return_total),
                'purchase_returns': float(purchase_return_total),
                'gross_profit': float(gross_profit),
                'net_profit': float(net_profit),
                'transaction_counts': {
                    'sales': sales_data['total_sales_count'] or 0,
                    'purchases': purchase_data['total_purchase_count'] or 0,
                    'expenses': expense_data['expense_count'] or 0,
                    'sales_returns': sales_return_query.count(),
                    'purchase_returns': purchase_return_query.count(),
                },
                'expense_breakdown': category_breakdown,
                'date_range': {
                    'start': start.isoformat() if start else None,
                    'end': end.isoformat() if end else None
                }
            }
            
            serializer = ProfitLossReportSerializer(data)
            return custom_response(True, "Profit & Loss report fetched successfully", serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)

class ExpenseReportView(BaseReportView):
    filter_serializer_class = ExpenseFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            expenses = Expense.objects.filter(company=company).select_related(
                'head', 'subhead'
            ).order_by('-expense_date')
            
            if start and end:
                expenses = expenses.filter(expense_date__range=[start, end])
            
            filter_q = Q()
            if filters.get('category'):
                filter_q &= Q(head_id=filters['category'])
            if filters.get('payment_method'):
                filter_q &= Q(payment_method=filters['payment_method'])
            
            expenses = expenses.filter(filter_q)
            
            if filters.get('min_amount'):
                expenses = expenses.filter(amount__gte=filters['min_amount'])
            if filters.get('max_amount'):
                expenses = expenses.filter(amount__lte=filters['max_amount'])
            
            report_data = []
            sl_number = 1
            for expense in expenses:
                report_data.append({
                    'sl': sl_number,
                    'id': expense.id,
                    'head': expense.head.name,
                    'subhead': expense.subhead.name if expense.subhead else None,
                    'amount': expense.amount,
                    'payment_method': expense.payment_method,
                    'expense_date': expense.expense_date,
                    'note': expense.note
                })
                sl_number += 1
            
            serializer = ExpenseSerializer(report_data, many=True)
            
            total_expenses = expenses.aggregate(total=Sum('amount', output_field=FloatField()))
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_count': expenses.count(),
                    'total_amount': total_expenses.get('total') or 0,
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Expense report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

class PurchaseReturnReportView(BaseReportView):
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            returns = PurchaseReturn.objects.filter(company=company)
            
            supplier_id = request.GET.get('supplier')
            if supplier_id:
                if hasattr(PurchaseReturn, 'purchase_ref'):
                    returns = returns.filter(purchase_ref__supplier_id=supplier_id)
                elif hasattr(PurchaseReturn, 'purchase'):
                    returns = returns.filter(purchase__supplier_id=supplier_id)
            
            if start and end:
                returns = returns.filter(date__range=[start, end])
            
            returns = returns.prefetch_related('items').order_by('-date')
            
            report_data = []
            sl_number = 1
            
            for return_obj in returns:
                total_amount = 0
                if hasattr(return_obj, 'items'):
                    for item in return_obj.items.all():
                        if hasattr(item, 'subtotal'):
                            total_amount += float(item.subtotal())
                
                return_amount = 0
                if hasattr(return_obj, 'return_amount') and return_obj.return_amount:
                    return_amount = float(return_obj.return_amount)
                else:
                    return_amount = total_amount
                
                supplier_name = "Unknown Supplier"
                invoice_no = "N/A"
                
                if hasattr(return_obj, 'purchase_ref') and return_obj.purchase_ref:
                    supplier_name = return_obj.purchase_ref.supplier.name if return_obj.purchase_ref.supplier else 'N/A'
                    invoice_no = return_obj.purchase_ref.invoice_no
                elif hasattr(return_obj, 'purchase') and return_obj.purchase:
                    supplier_name = return_obj.purchase.supplier.name if return_obj.purchase.supplier else 'N/A'
                    invoice_no = return_obj.purchase.invoice_no
                
                report_data.append({
                    'sl': sl_number,
                    'invoice_no': invoice_no,
                    'supplier': supplier_name,
                    'total_amount': total_amount,
                    'return_amount': return_amount,
                    'date': return_obj.date
                })
                sl_number += 1
            
            serializer = PurchaseReturnReportSerializer(report_data, many=True)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_count': len(report_data),
                    'total_return_amount': sum(item['return_amount'] for item in report_data),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Purchase return report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

class SalesReturnReportView(BaseReportView):
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            sales_returns = SalesReturn.objects.filter(company=company)
            
            customer_id = request.GET.get('customer')
            if customer_id:
                if hasattr(SalesReturn, 'customer'):
                    sales_returns = sales_returns.filter(customer_id=customer_id)
                elif hasattr(SalesReturn, 'sale__customer'):
                    sales_returns = sales_returns.filter(sale__customer_id=customer_id)
            
            if start and end:
                sales_returns = sales_returns.filter(return_date__range=[start, end])
            
            sales_returns = sales_returns.prefetch_related('items').order_by('-return_date')
            
            report_data = []
            sl_number = 1
            
            for sr in sales_returns:
                total_amount = 0
                for item in sr.items.all():
                    item_total = (item.quantity or 0) * (item.unit_price or 0)
                    total_amount += float(item_total)
                
                discount = float(getattr(sr, 'discount', 0) or 0)
                vat = float(getattr(sr, 'vat', 0) or 0)
                service_charge = float(getattr(sr, 'service_charge', 0) or 0)
                delivery_charge = float(getattr(sr, 'delivery_charge', 0) or 0)
                
                return_amount = total_amount - discount + vat + service_charge + delivery_charge
                
                customer_name = "Unknown Customer"
                if hasattr(sr, 'customer') and sr.customer:
                    customer_name = sr.customer.name
                elif hasattr(sr, 'sale') and sr.sale and sr.sale.customer:
                    customer_name = sr.sale.customer.name
                
                report_data.append({
                    'sl': sl_number,
                    'invoice_no': getattr(sr, 'invoice_no', f"SR-{sr.id}"),
                    'customer': customer_name,
                    'total_amount': total_amount,
                    'return_amount': return_amount,
                    'date': sr.return_date
                })
                sl_number += 1
            
            serializer = SalesReturnReportSerializer(report_data, many=True)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_count': len(report_data),
                    'total_return_amount': sum(item['return_amount'] for item in report_data),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Sales return report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

class BadStockReportView(BaseReportView):
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            bad_items = BadStock.objects.filter(company=company).select_related('product')
            
            if start and end:
                bad_items = bad_items.filter(created_at__date__range=[start, end])
            
            reason = request.GET.get('reason')
            if reason:
                bad_items = bad_items.filter(reason__icontains=reason)
            
            report_data = []
            sl_number = 1
            
            for item in bad_items:
                report_data.append({
                    'sl': sl_number,
                    'product': item.product.name,
                    'quantity': item.quantity,
                    'reason': item.reason
                })
                sl_number += 1
            
            serializer = BadStockReportSerializer(report_data, many=True)
            
            response_data = {
                'report': serializer.data,
                'summary': {
                    'total_bad_stock_items': len(report_data),
                    'total_quantity': sum(item['quantity'] for item in report_data),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    }
                }
            }
            
            return custom_response(True, "Bad stock report fetched successfully", response_data)
            
        except Exception as e:
            return self.handle_exception(e)

class DashboardSummaryView(BaseReportView):
    @method_decorator(cache_page(300))
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            today = timezone.now().date()
            
            # Sales metrics
            today_sales = Sale.objects.filter(
                company=company, 
                sale_date__date=today
            ).aggregate(
                total=Sum('grand_total'),
                count=Count('id')
            )
            
            # Purchase metrics
            today_purchases = Purchase.objects.filter(
                company=company,
                purchase_date=today
            ).aggregate(
                total=Sum('grand_total'),
                count=Count('id')
            )
            
            # Expense metrics
            today_expenses = Expense.objects.filter(
                company=company,
                expense_date=today
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            # Stock alerts
            low_stock_count = Product.objects.filter(
                company=company,
                stock_qty__lte=F('alert_quantity'),
                stock_qty__gt=0
            ).count()
            
            out_of_stock_count = Product.objects.filter(
                company=company,
                stock_qty=0
            ).count()
            
            # Recent activities
            recent_sales = Sale.objects.filter(
                company=company
            ).select_related('customer').order_by('-sale_date')[:5]
            
            recent_purchases = Purchase.objects.filter(
                company=company
            ).select_related('supplier').order_by('-purchase_date')[:5]
            
            dashboard_data = {
                'today_metrics': {
                    'sales': {
                        'total': float(today_sales['total'] or 0),
                        'count': today_sales['count'] or 0
                    },
                    'purchases': {
                        'total': float(today_purchases['total'] or 0),
                        'count': today_purchases['count'] or 0
                    },
                    'expenses': {
                        'total': float(today_expenses['total'] or 0),
                        'count': today_expenses['count'] or 0
                    }
                },
                'stock_alerts': {
                    'low_stock': low_stock_count,
                    'out_of_stock': out_of_stock_count
                },
                'recent_activities': {
                    'sales': [
                        {
                            'invoice_no': sale.invoice_no,
                            'customer': sale.customer.name if sale.customer else "Walk-in",
                            'amount': float(sale.grand_total),
                            'date': sale.sale_date.date()
                        } for sale in recent_sales
                    ],
                    'purchases': [
                        {
                            'invoice_no': purchase.invoice_no,
                            'supplier': purchase.supplier.name,
                            'amount': float(purchase.grand_total),
                            'date': purchase.purchase_date
                        } for purchase in recent_purchases
                    ]
                }
            }
            
            return custom_response(True, "Dashboard data fetched successfully", dashboard_data)
            
        except Exception as e:
            return self.handle_exception(e)