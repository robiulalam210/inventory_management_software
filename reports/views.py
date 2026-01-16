# reports/views.py - COMPLETE UPDATED VERSION
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F, FloatField, Count, Q, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from returns.models import SalesReturn, PurchaseReturn, BadStock,SalesReturnItem, PurchaseReturnItem
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

from django.db.models import Q  
from django.utils.timezone import make_aware
from django.db.models import Sum, Count, F, FloatField, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.expressions import ExpressionWrapper
from datetime import datetime
from django.db.models import Sum, Count, F
from datetime import datetime
from django.utils import timezone
from returns.models import PurchaseReturn

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
            
            # ===== DEBUG LOGS =====
            print(f"=== SALES REPORT DEBUG ===")
            print(f"Company ID: {company.id}")
            print(f"Request GET params: {dict(request.GET)}")
            print(f"Parsed start date: {start}")
            print(f"Parsed end date: {end}")
            print(f"Filters: {filters}")
            
            sales = Sale.objects.filter(company=company).select_related(
                'customer', 'sale_by'
            ).prefetch_related(
                'items', 'items__product'
            ).order_by('-sale_date')
            
            print(f"Total sales in company (before filters): {sales.count()}")
            
            # ===== FIXED DATE FILTERING =====
            if start and end:
                print(f"Applying date filter: {start} to {end}")
                
                # IMPORTANT: Convert dates to datetimes for proper comparison
                # Since sale_date is DateTimeField, we need to use __range with datetimes
                start_datetime = datetime.combine(start, datetime.min.time())
                end_datetime = datetime.combine(end, datetime.max.time())
                
                print(f"Start datetime: {start_datetime}")
                print(f"End datetime: {end_datetime}")
                
                # Option 1: Use __range with datetimes (recommended)
                sales = sales.filter(sale_date__range=[start_datetime, end_datetime])
                
                print(f"Sales after date filter: {sales.count()}")
                
                # DEBUG: Check what dates are actually in the filtered sales
                if sales.exists():
                    print("Sample sales dates after filter:")
                    for sale in sales[:5]:  # First 5
                        print(f"  - {sale.invoice_no}: {sale.sale_date}")
                else:
                    print("No sales found with date filter!")
                    
                    # DEBUG: Check if sales exist outside the filter range
                    all_sales = Sale.objects.filter(company=company)
                    print(f"All sales dates in database (first 10):")
                    for sale in all_sales.order_by('sale_date')[:10]:
                        print(f"  - {sale.invoice_no}: {sale.sale_date} (Year: {sale.sale_date.year})")
            
            # ===== OTHER FILTERS =====
            filter_q = Q()
            if filters.get('customer'):
                filter_q &= Q(customer_id=filters['customer'])
                print(f"Applying customer filter: {filters['customer']}")
            if filters.get('payment_status'):
                filter_q &= Q(payment_status=filters['payment_status'])
                print(f"Applying payment status filter: {filters['payment_status']}")
            if filters.get('sale_type'):
                filter_q &= Q(sale_type=filters['sale_type'])
                print(f"Applying sale type filter: {filters['sale_type']}")
            if filters.get('invoice_no'):
                filter_q &= Q(invoice_no__icontains=filters['invoice_no'])
                print(f"Applying invoice no filter: {filters['invoice_no']}")
            
            sales = sales.filter(filter_q)
            print(f"Sales after all filters: {sales.count()}")
            
            # ===== BUILD REPORT DATA =====
            report_data = []
            sl_number = 1
            
            for sale in sales:
                sales_price = 0.0
                cost_price = 0.0
                
                # Calculate totals from items
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
                
                # Apply amount filters if provided
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
            
            print(f"Final report data count: {len(report_data)}")
            
            # ===== RETURN RESPONSE =====
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
            
            print(f"=== END SALES REPORT DEBUG ===\n")
            
            return custom_response(True, "Sales report fetched successfully", response_data)
            
        except Exception as e:
            print(f"ERROR in SalesReportView: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.handle_exception(e)
    
    def _build_sales_summary(self, report_data, date_range):
        if not report_data:
            print("No report data to build summary")
            return {
                'total_sales': 0, 
                'total_cost': 0, 
                'total_profit': 0,
                'total_collected': 0, 
                'total_due': 0, 
                'average_profit_margin': 0,
                'total_transactions': 0,
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
# Top Sold Products Report - FIXED VERSION
# --------------------
class TopSoldProductsReportView(BaseReportView):
    @method_decorator(cache_page(600))
    def get(self, request):
        try:
            company = self.get_company(request)
            start, end = self.get_date_range(request)
            
            # Debug logs
            print(f"=== TOP PRODUCTS DEBUG ===")
            print(f"Company: {company.id}")
            print(f"Date range: {start} to {end}")
            print(f"GET params: {dict(request.GET)}")
            
            # First get sale items for the date range
            sale_items_query = SaleItem.objects.filter(
                sale__company=company
            ).select_related('product', 'product__category', 'product__brand')
            
            # Apply date filter correctly
            if start and end:
                # Convert dates to datetimes for proper comparison
                start_datetime = datetime.combine(start, datetime.min.time())
                end_datetime = datetime.combine(end, datetime.max.time())
                sale_items_query = sale_items_query.filter(
                    sale__sale_date__range=[start_datetime, end_datetime]
                )
            
            # Apply category filter
            category_id = request.GET.get('category')
            if category_id:
                sale_items_query = sale_items_query.filter(product__category_id=category_id)
            
            # Get limit
            limit = int(request.GET.get('limit', 10))
            
            # Group by product and aggregate
            product_stats = sale_items_query.values(
                'product__id',
                'product__name',
                'product__selling_price',
                'product__purchase_price',
                'product__stock_qty'
            ).annotate(
                total_quantity_sold=Coalesce(Sum('quantity'), 0),
                total_sales_amount=Coalesce(
                    Sum(F('quantity') * F('unit_price')),
                    0,
                    output_field=FloatField()
                )
            ).order_by('-total_quantity_sold')[:limit]
            
            print(f"Found {len(product_stats)} products with sales data")
            
            # Prepare report data
            report_data = []
            sl_number = 1
            
            for stat in product_stats:
                # Calculate profit
                purchase_price = stat.get('product__purchase_price', 0) or 0
                selling_price = stat.get('product__selling_price', 0) or 0
                profit_per_unit = selling_price - purchase_price
                total_profit = profit_per_unit * stat['total_quantity_sold']
                
                report_data.append({
                    'sl': sl_number,
                    'product_name': stat['product__name'],
                    'selling_price': float(selling_price),
                    'purchase_price': float(purchase_price),
                    'total_sold_quantity': stat['total_quantity_sold'],
                    'total_sold_price': float(stat['total_sales_amount']),
                    'total_profit': float(total_profit),
                    'current_stock': stat.get('product__stock_qty', 0),
                    'product_id': stat['product__id']
                })
                sl_number += 1
            
            # If no data found, show all products with zero sales
            if not report_data:
                print("No sales found, showing all products...")
                products = Product.objects.filter(company=company).order_by('-stock_qty')[:limit]
                
                for product in products:
                    report_data.append({
                        'sl': sl_number,
                        'product_name': product.name,
                        'selling_price': float(product.selling_price or 0),
                        'purchase_price': float(product.purchase_price or 0),
                        'total_sold_quantity': 0,
                        'total_sold_price': 0,
                        'total_profit': 0,
                        'current_stock': product.stock_qty,
                        'product_id': product.id
                    })
                    sl_number += 1
            
            serializer = TopSoldProductsSerializer(report_data, many=True)
            
            # Calculate summary
            total_quantity = sum(item['total_sold_quantity'] for item in report_data)
            total_sales = sum(item['total_sold_price'] for item in report_data)
            total_profit = sum(item['total_profit'] for item in report_data)
            
            response_data = {
                'report': serializer.data,
                'summary': {
                    'total_products': len(report_data),
                    'total_quantity_sold': total_quantity,
                    'total_sales_amount': round(total_sales, 2),
                    'total_profit': round(total_profit, 2),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    },
                    'limit_used': limit
                }
            }
            
            print(f"=== END TOP PRODUCTS DEBUG ===\n")
            
            return custom_response(True, "Top sold products report fetched successfully", response_data)
            
        except Exception as e:
            print(f"ERROR in TopSoldProductsReportView: {str(e)}")
            import traceback
            traceback.print_exc()
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
            
            # 3. Purchase Return transactions - CORRECTED SECTION
            if filters.get('transaction_type') in ['all', 'return']:
                purchase_returns = PurchaseReturn.objects.filter(company=company)
                
                # Filter by supplier - multiple possible relationships
                if hasattr(PurchaseReturn, 'purchase_ref'):
                    purchase_returns = purchase_returns.filter(purchase_ref__supplier=supplier)
                elif hasattr(PurchaseReturn, 'purchase'):
                    purchase_returns = purchase_returns.filter(purchase__supplier=supplier)
                elif hasattr(PurchaseReturn, 'supplier'):
                    # Direct supplier relationship
                    purchase_returns = purchase_returns.filter(supplier=supplier)
                
                # Use return_date instead of date for filtering and ordering
                if start and end:
                    purchase_returns = purchase_returns.filter(return_date__range=[start, end])
                
                for return_obj in purchase_returns.order_by('return_date'):  # Use return_date for ordering
                    return_amount = 0
                    
                    # Calculate return amount from items if available
                    if hasattr(return_obj, 'items') and hasattr(return_obj.items, 'all'):
                        for item in return_obj.items.all():
                            if hasattr(item, 'subtotal'):
                                return_amount += float(item.subtotal())
                            elif hasattr(item, 'amount'):
                                return_amount += float(item.amount)
                    
                    # Use return_amount field if items are not available
                    if return_amount == 0 and hasattr(return_obj, 'return_amount'):
                        return_amount = float(return_obj.return_amount)
                    
                    running_balance -= return_amount
                    
                    # Get reference number
                    reference_no = "RET-UNKNOWN"
                    if hasattr(return_obj, 'invoice_no') and return_obj.invoice_no:
                        reference_no = return_obj.invoice_no
                    elif hasattr(return_obj, 'purchase_ref') and return_obj.purchase_ref:
                        reference_no = f"RET-{return_obj.purchase_ref.invoice_no}"
                    elif hasattr(return_obj, 'purchase') and return_obj.purchase:
                        reference_no = f"RET-{return_obj.purchase.invoice_no}"
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': reference_no,
                        'date': return_obj.return_date,  # Use return_date here
                        'particular': 'Return',
                        'details': 'Purchase Return',
                        'type': 'Return',
                        'method': getattr(return_obj, 'payment_method', 'N/A'),
                        'debit': 0.0,
                        'credit': round(return_amount, 2),
                        'due': round(running_balance, 2),
                        'supplier_id': supplier.id,
                        'supplier_name': supplier.name
                    })
                    sl_number += 1
            
            # 4. Opening balance (if needed for the period)
            if filters.get('include_opening_balance', True):
                # Calculate opening balance before the start date
                opening_balance = 0
                
                # Purchases before start date
                opening_purchases = Purchase.objects.filter(
                    company=company,
                    supplier=supplier
                )
                if start:
                    opening_purchases = opening_purchases.filter(purchase_date__lt=start)
                for purchase in opening_purchases:
                    opening_balance += float(purchase.grand_total)
                
                # Payments before start date
                try:
                    from suppliers.models import SupplierPayment
                    opening_payments = SupplierPayment.objects.filter(
                        company=company,
                        supplier=supplier
                    )
                    if start:
                        opening_payments = opening_payments.filter(payment_date__lt=start)
                    for payment in opening_payments:
                        opening_balance -= float(payment.amount)
                except ImportError:
                    pass
                
                # Purchase returns before start date
                opening_returns = PurchaseReturn.objects.filter(company=company)
                if hasattr(PurchaseReturn, 'purchase_ref'):
                    opening_returns = opening_returns.filter(purchase_ref__supplier=supplier)
                elif hasattr(PurchaseReturn, 'purchase'):
                    opening_returns = opening_returns.filter(purchase__supplier=supplier)
                elif hasattr(PurchaseReturn, 'supplier'):
                    opening_returns = opening_returns.filter(supplier=supplier)
                
                if start:
                    opening_returns = opening_returns.filter(return_date__lt=start)
                
                for return_obj in opening_returns:
                    return_amount = 0
                    if hasattr(return_obj, 'items') and hasattr(return_obj.items, 'all'):
                        for item in return_obj.items.all():
                            if hasattr(item, 'subtotal'):
                                return_amount += float(item.subtotal())
                    elif hasattr(return_obj, 'return_amount'):
                        return_amount = float(return_obj.return_amount)
                    opening_balance -= return_amount
                
                # Add opening balance as first entry if non-zero
                if opening_balance != 0:
                    ledger_entries.insert(0, {
                        'sl': 0,
                        'voucher_no': 'OPENING',
                        'date': start if start else datetime.now().date(),
                        'particular': 'Opening Balance',
                        'details': 'Balance brought forward',
                        'type': 'Opening',
                        'method': 'N/A',
                        'debit': round(opening_balance, 2) if opening_balance > 0 else 0.0,
                        'credit': round(abs(opening_balance), 2) if opening_balance < 0 else 0.0,
                        'due': round(opening_balance, 2),
                        'supplier_id': supplier.id,
                        'supplier_name': supplier.name
                    })
                    running_balance += opening_balance
            
            # Sort all entries by date
            ledger_entries.sort(key=lambda x: x['date'])
            
            # Re-number SL after sorting
            for i, entry in enumerate(ledger_entries, 1):
                entry['sl'] = i
            
            # Recalculate running balance after sorting
            current_balance = 0
            for entry in ledger_entries:
                if entry['type'] == 'Opening':
                    current_balance = entry['due']
                else:
                    current_balance += entry['debit'] - entry['credit']
                    entry['due'] = round(current_balance, 2)
            
            serializer = SupplierLedgerSerializer(ledger_entries, many=True)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.name,
                    'opening_balance': round(ledger_entries[0]['due'] - ledger_entries[0]['debit'] + ledger_entries[0]['credit'] if ledger_entries else 0, 2),
                    'closing_balance': round(current_balance, 2),
                    'total_debit': round(sum(entry['debit'] for entry in ledger_entries), 2),
                    'total_credit': round(sum(entry['credit'] for entry in ledger_entries), 2),
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
# Customer Due & Advance Report - FIXED VERSION
# --------------------
class CustomerDueAdvanceReportView(BaseReportView):
    filter_serializer_class = CustomerDueAdvanceFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            print(f"=== CUSTOMER DUE DEBUG ===")
            print(f"Company: {company.id}")
            print(f"Filters: {filters}")
            print(f"Date range: {start} to {end}")
            
            from customers.models import Customer
            customers = Customer.objects.filter(company=company, is_active=True)
            
            if filters.get('customer'):
                customers = customers.filter(id=filters['customer'])
                print(f"Filtered by customer ID: {filters['customer']}")
            
            print(f"Total active customers: {customers.count()}")
            
            report_data = []
            sl_number = 1
            
            for customer in customers:
                # Get sales for this customer
                sales_query = Sale.objects.filter(
                    company=company, 
                    customer=customer
                )
                
                # Apply date range filter
                if start and end:
                    start_datetime = datetime.combine(start, datetime.min.time())
                    end_datetime = datetime.combine(end, datetime.max.time())
                    sales_query = sales_query.filter(sale_date__range=[start_datetime, end_datetime])
                
                # Get totals - FIXED with output_field
                sales_totals = sales_query.aggregate(
                    total_sales=Coalesce(Sum('grand_total', output_field=FloatField()), 0.0),
                    total_received=Coalesce(Sum('paid_amount', output_field=FloatField()), 0.0),
                    total_discount=Coalesce(Sum('overall_discount', output_field=FloatField()), 0.0),
                    count=Count('id')
                )
                
                # Convert to float
                total_sales = float(sales_totals['total_sales'] or 0)
                total_received = float(sales_totals['total_received'] or 0)
                total_discount = float(sales_totals['total_discount'] or 0)
                
                # Calculate due and advance
                net_sales = total_sales - total_discount
                present_due = max(0.0, net_sales - total_received)
                present_advance = max(0.0, total_received - net_sales)
                
                print(f"Customer {customer.name}: Sales={net_sales}, Received={total_received}, Due={present_due}, Advance={present_advance}")
                
                # Apply status filter
                status_filter = filters.get('status', 'all')
                
                if status_filter == 'due' and present_due <= 0:
                    continue  # Skip if no due and filter is for due only
                elif status_filter == 'advance' and present_advance <= 0:
                    continue  # Skip if no advance and filter is for advance only
                elif status_filter == 'all' and present_due == 0 and present_advance == 0 and total_sales == 0:
                    # Skip customers with no activity if showing all
                    continue
                
                # Get payment summary if needed
                try:
                    from money_receipts.models import MoneyReceipt
                    payments = MoneyReceipt.objects.filter(
                        company=company,
                        customer=customer
                    )
                    if start and end:
                        start_datetime = datetime.combine(start, datetime.min.time())
                        end_datetime = datetime.combine(end, datetime.max.time())
                        payments = payments.filter(payment_date__range=[start_datetime, end_datetime])
                    
                    total_payments = payments.aggregate(
                        total=Coalesce(Sum('amount', output_field=FloatField()), 0.0)
                    )['total'] or 0
                except ImportError:
                    total_payments = 0
                
                # Add to report
                report_data.append({
                    'sl': sl_number,
                    'customer_no': customer.id,
                    'customer_name': customer.name,
                    'phone': customer.phone or 'N/A',
                    'email': customer.email or 'N/A',
                    'total_sales': round(net_sales, 2),
                    'total_received': round(total_received, 2),
                    'present_due': round(present_due, 2),
                    'present_advance': round(present_advance, 2),
                    'total_transactions': sales_totals['count'],
                    'total_payments': round(float(total_payments), 2),
                    'customer_id': customer.id
                })
                sl_number += 1
            
            # Sort based on filter
            if filters.get('status') == 'due':
                report_data.sort(key=lambda x: x['present_due'], reverse=True)
            elif filters.get('status') == 'advance':
                report_data.sort(key=lambda x: x['present_advance'], reverse=True)
            else:
                report_data.sort(key=lambda x: max(x['present_due'], x['present_advance']), reverse=True)
            
            # Update SL numbers after sorting
            for i, item in enumerate(report_data, 1):
                item['sl'] = i
            
            print(f"Final report items: {len(report_data)}")
            
            serializer = CustomerDueAdvanceSerializer(report_data, many=True)
            
            # Calculate summary
            total_customers = len(report_data)
            total_overall_due = sum(item['present_due'] for item in report_data)
            total_overall_advance = sum(item['present_advance'] for item in report_data)
            total_overall_sales = sum(item['total_sales'] for item in report_data)
            total_overall_received = sum(item['total_received'] for item in report_data)
            
            response_data = {
                'report': self.paginate_data(serializer.data),
                'summary': {
                    'total_customers': total_customers,
                    'total_sales_amount': round(total_overall_sales, 2),
                    'total_received_amount': round(total_overall_received, 2),
                    'total_due_amount': round(total_overall_due, 2),
                    'total_advance_amount': round(total_overall_advance, 2),
                    'net_balance': round(total_overall_advance - total_overall_due, 2),
                    'date_range': {
                        'start': start.isoformat() if start else None,
                        'end': end.isoformat() if end else None
                    },
                    'filter_status': filters.get('status', 'all')
                }
            }
            
            print(f"=== END CUSTOMER DUE DEBUG ===\n")
            
            return custom_response(True, "Customer due & advance report fetched successfully", response_data)
            
        except Exception as e:
            print(f"ERROR in CustomerDueAdvanceReportView: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.handle_exception(e)
        

# --------------------
# Customer Ledger Details - ASCII-SAFE VERSION
# --------------------
class CustomerLedgerReportView(BaseReportView):
    filter_serializer_class = CustomerLedgerFilterSerializer
    
    def get(self, request):
        try:
            company = self.get_company(request)
            filters = self.get_filters(request)
            start, end = self.get_date_range(request)
            
            # ASCII-safe debug output
            print("\n=== CUSTOMER LEDGER DEBUG ===")
            print(f"Company ID: {company.id}")
            print(f"Customer ID from filters: {filters.get('customer')}")
            print(f"Date range: {start} to {end}")
            
            if not filters.get('customer'):
                return custom_response(False, "Customer ID is required for ledger report", None, 400)
            
            from customers.models import Customer
            
            # ASCII-safe customer lookup
            try:
                customer = Customer.objects.get(id=filters['customer'], company=company)
                print(f"[SUCCESS] Found customer: {customer.name} (ID: {customer.id})")
            except Customer.DoesNotExist:
                return custom_response(False, "Customer not found", None, 404)
            
            ledger_entries = []
            running_balance = 0.0
            sl_number = 1
            
            # 1. Sale transactions - NO DATE FILTER FOR NOW
            if filters.get('transaction_type') in ['all', 'sale']:
                sales = Sale.objects.filter(
                    company=company, 
                    customer=customer
                ).select_related('customer').order_by('sale_date')
                
                print(f"\n--- SALES FOR CUSTOMER ---")
                print(f"Total sales count: {sales.count()}")
                
                # Show all sales without date filter
                sale_counter = 0
                for sale in sales:
                    sale_counter += 1
                    sale_amount = 0.0
                    if sale.grand_total:
                        try:
                            sale_amount = float(sale.grand_total)
                        except (TypeError, ValueError):
                            sale_amount = 0.0
                    
                    running_balance += sale_amount
                    
                    # ASCII-safe date formatting
                    sale_date_str = "N/A"
                    if sale.sale_date:
                        try:
                            sale_date_str = sale.sale_date.strftime('%Y-%m-%d')
                        except:
                            sale_date_str = str(sale.sale_date)[:10]
                    
                    print(f"Sale {sale_counter}: {sale.invoice_no} - Date: {sale_date_str} - Amount: ${sale_amount}")
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': sale.invoice_no,
                        'date': sale.sale_date.date() if sale.sale_date else datetime.now().date(),
                        'particular': 'Sale',
                        'details': f'Sale - {sale.invoice_no}',
                        'type': 'Sale',
                        'method': sale.payment_method or 'N/A',
                        'debit': round(sale_amount, 2),
                        'credit': 0.0,
                        'due': round(running_balance, 2),
                        'customer_id': customer.id,
                        'customer_name': customer.name
                    })
                    sl_number += 1
                
                if sale_counter == 0:
                    print("No sales found for this customer")
            
            # 2. Payment transactions
            if filters.get('transaction_type') in ['all', 'payment']:
                try:
                    from money_receipts.models import MoneyReceipt
                    
                    payments = MoneyReceipt.objects.filter(company=company)
                    
                    # Filter by customer
                    if hasattr(MoneyReceipt, 'customer'):
                        payments = payments.filter(customer=customer)
                        print(f"\n--- PAYMENTS FOR CUSTOMER ---")
                        print(f"Filtering by customer field")
                    elif hasattr(MoneyReceipt, 'customer_id'):
                        payments = payments.filter(customer_id=customer.id)
                        print(f"\n--- PAYMENTS FOR CUSTOMER ---")
                        print(f"Filtering by customer_id field")
                    elif hasattr(MoneyReceipt, 'customer_name'):
                        payments = payments.filter(customer_name__icontains=customer.name)
                        print(f"\n--- PAYMENTS FOR CUSTOMER ---")
                        print(f"Filtering by customer_name field")
                    else:
                        print(f"\n--- PAYMENTS FOR CUSTOMER ---")
                        print(f"MoneyReceipt model doesn't have customer-related fields")
                        payments = MoneyReceipt.objects.none()
                    
                    print(f"Total payments count: {payments.count()}")
                    
                    payment_counter = 0
                    for payment in payments.order_by('id'):
                        payment_counter += 1
                        payment_amount = 0.0
                        if hasattr(payment, 'amount') and payment.amount:
                            try:
                                payment_amount = float(payment.amount)
                            except (TypeError, ValueError):
                                payment_amount = 0.0
                        
                        running_balance -= payment_amount
                        
                        # Get voucher number
                        voucher_no = getattr(payment, 'mr_no', 
                                           getattr(payment, 'voucher_no', 
                                                   getattr(payment, 'invoice_no', 
                                                           f"PYMT-{payment.id}")))
                        
                        # ASCII-safe output
                        print(f"Payment {payment_counter}: {voucher_no} - Amount: ${payment_amount}")
                        
                        # Get date
                        payment_date = None
                        if hasattr(payment, 'payment_date'):
                            payment_date = payment.payment_date
                        elif hasattr(payment, 'date'):
                            payment_date = payment.date
                        
                        ledger_entries.append({
                            'sl': sl_number,
                            'voucher_no': voucher_no,
                            'date': payment_date.date() if payment_date else datetime.now().date(),
                            'particular': 'Payment',
                            'details': f'Payment - {getattr(payment, "payment_method", "N/A")}',
                            'type': 'Payment',
                            'method': getattr(payment, 'payment_method', 'N/A'),
                            'debit': 0.0,
                            'credit': round(payment_amount, 2),
                            'due': round(running_balance, 2),
                            'customer_id': customer.id,
                            'customer_name': customer.name
                        })
                        sl_number += 1
                    
                    if payment_counter == 0:
                        print("No payments found for this customer")
                        
                except ImportError as e:
                    print(f"\n--- PAYMENTS ---")
                    print(f"MoneyReceipt model not available: {e}")
                except Exception as e:
                    print(f"\n--- PAYMENTS ERROR ---")
                    print(f"Error: {str(e)}")
            
            # 3. Sales Return transactions
            if filters.get('transaction_type') in ['all', 'return']:
                sales_returns = SalesReturn.objects.filter(company=company)
                
                print(f"\n--- SALES RETURNS FOR CUSTOMER ---")
                
                # Filter by customer
                if hasattr(SalesReturn, 'customer'):
                    sales_returns = sales_returns.filter(customer=customer)
                    print(f"Filtering by direct customer relationship")
                elif hasattr(SalesReturn, 'sale__customer'):
                    sales_returns = sales_returns.filter(sale__customer=customer)
                    print(f"Filtering by sale__customer relationship")
                else:
                    print(f"No customer relationship found in SalesReturn model")
                    sales_returns = SalesReturn.objects.none()
                
                print(f"Total returns count: {sales_returns.count()}")
                
                return_counter = 0
                for return_obj in sales_returns.order_by('id'):
                    return_counter += 1
                    return_amount = 0.0
                    
                    if hasattr(return_obj, 'return_amount') and return_obj.return_amount:
                        try:
                            return_amount = float(return_obj.return_amount)
                        except (TypeError, ValueError):
                            return_amount = 0.0
                    elif hasattr(return_obj, 'grand_total') and return_obj.grand_total:
                        try:
                            return_amount = float(return_obj.grand_total)
                        except (TypeError, ValueError):
                            return_amount = 0.0
                    
                    running_balance -= return_amount
                    
                    voucher_no = getattr(return_obj, 'invoice_no', 
                                       getattr(return_obj, 'return_no', 
                                               f"RET-{return_obj.id}"))
                    
                    print(f"Return {return_counter}: {voucher_no} - Amount: ${return_amount}")
                    
                    ledger_entries.append({
                        'sl': sl_number,
                        'voucher_no': voucher_no,
                        'date': return_obj.return_date,
                        'particular': 'Return',
                        'details': 'Sales Return',
                        'type': 'Return',
                        'method': getattr(return_obj, 'payment_method', 'N/A'),
                        'debit': 0.0,
                        'credit': round(return_amount, 2),
                        'due': round(running_balance, 2),
                        'customer_id': customer.id,
                        'customer_name': customer.name
                    })
                    sl_number += 1
                
                if return_counter == 0:
                    print("No returns found for this customer")
            
            # Sort all entries by date
            ledger_entries.sort(key=lambda x: x['date'])
            
            # Re-number SL after sorting
            for i, entry in enumerate(ledger_entries, 1):
                entry['sl'] = i
            
            print(f"\n=== LEDGER SUMMARY ===")
            print(f"Total ledger entries: {len(ledger_entries)}")
            print(f"Final running balance: {running_balance}")
            
            if ledger_entries:
                print("First 5 entries:")
                for i, entry in enumerate(ledger_entries[:5], 1):
                    print(f"  {i}. {entry['date']} - {entry['type']} - {entry['voucher_no']}")
            else:
                print("No ledger entries found!")
                
                # Additional debug
                print(f"\n=== ADDITIONAL DEBUG ===")
                print(f"Customer: {customer.name} (ID: {customer.id})")
                print(f"Company: {company.id}")
                
                # Check if any sales exist at all
                all_sales_in_company = Sale.objects.filter(company=company).count()
                print(f"All sales in company: {all_sales_in_company}")
                
                # Check sales with this customer ID (regardless of company)
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM sales_sale WHERE customer_id = %s", [customer.id])
                    row = cursor.fetchone()
                    print(f"All sales with customer ID {customer.id}: {row[0]}")
            
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
            
            print(f"\n=== END DEBUG ===\n")
            
            return custom_response(True, "Customer ledger report fetched successfully", response_data)
            
        except Exception as e:
            # ASCII-safe error message
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            print(f"ERROR in CustomerLedgerReportView: {error_msg}")
            import traceback
            traceback.print_exc()
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
                sales_query = sales_query.filter(sale_date__range=[start, end])  # Fixed: removed extra __date
            
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
            
            # Return data - FIXED: Use return_date for both SalesReturn and PurchaseReturn
            sales_return_query = SalesReturn.objects.filter(company=company)
            purchase_return_query = PurchaseReturn.objects.filter(company=company)
            
            if start and end:
                sales_return_query = sales_return_query.filter(return_date__range=[start, end])
                purchase_return_query = purchase_return_query.filter(return_date__range=[start, end])  # FIXED: changed date to return_date
            
            # Calculate sales return total - UPDATED for new model structure
            sales_return_total = 0
            for sales_return in sales_return_query:
                # Calculate from items
                items_total = sum([
                    float(item.total) if hasattr(item, 'total') and item.total else 
                    (float(item.quantity or 0) * float(item.unit_price or 0)) - float(item.discount or 0)
                    for item in sales_return.items.all()
                ])
                
                # Add return charge
                return_charge = float(getattr(sales_return, 'return_charge', 0) or 0)
                if sales_return.return_charge_type == 'percentage' and return_charge > 0:
                    return_charge_amount = (items_total * return_charge) / 100
                else:
                    return_charge_amount = return_charge
                
                return_amount = items_total + return_charge_amount
                sales_return_total += return_amount
            
            # Calculate purchase return total - UPDATED for new model structure
            purchase_return_total = 0
            for purchase_return in purchase_return_query:
                # Use return_amount field if available, otherwise calculate from items
                if purchase_return.return_amount:
                    purchase_return_total += float(purchase_return.return_amount)
                else:
                    # Calculate from items
                    items_total = sum([
                        float(item.total) if hasattr(item, 'total') and item.total else 
                        (float(item.quantity or 0) * float(item.unit_price or 0)) - float(item.discount or 0)
                        for item in purchase_return.items.all()
                    ])
                    
                    # Add return charge
                    return_charge = float(getattr(purchase_return, 'return_charge', 0) or 0)
                    if purchase_return.return_charge_type == 'percentage' and return_charge > 0:
                        return_charge_amount = (items_total * return_charge) / 100
                    else:
                        return_charge_amount = return_charge
                    
                    purchase_return_total += items_total + return_charge_amount
            
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
            
            # Serialize the actual Expense objects, not the dictionary
            serializer = ExpenseSerializer(expenses, many=True)
            
            # Transform the serialized data to include SL numbers
            report_data = []
            for index, expense_data in enumerate(serializer.data, 1):
                report_data.append({
                    'sl': index,
                    **expense_data
                })
            
            total_expenses = expenses.aggregate(total=Sum('amount', output_field=FloatField()))
            
            response_data = {
                'report': self.paginate_data(report_data),
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
                # Since your PurchaseReturn model has a direct supplier field (CharField)
                # You can't filter by supplier_id. If you need to filter by supplier name:
                from purchases.models import Purchase  # Import if you need to reference purchase model
                # If you want to filter by supplier name pattern:
                # returns = returns.filter(supplier__icontains=supplier_id)
                pass
            
            # FIX: Use return_date instead of date
            if start and end:
                returns = returns.filter(return_date__range=[start, end])
            
            # FIX: Order by return_date instead of date
            returns = returns.prefetch_related('items').order_by('-return_date')
            
            report_data = []
            sl_number = 1
            
            for return_obj in returns:
                # Calculate total from items
                total_amount = 0
                for item in return_obj.items.all():
                    # Calculate item total based on your model fields
                    base_amount = float(item.unit_price) * float(item.quantity)
                    
                    # Apply discount
                    if item.discount_type == 'percentage' and item.discount > 0:
                        discount_amount = (base_amount * float(item.discount)) / 100
                    else:
                        discount_amount = float(item.discount)
                    
                    item_total = base_amount - discount_amount
                    total_amount += item_total
                
                # Use return_amount from model or calculated total
                return_amount = float(return_obj.return_amount) if return_obj.return_amount else total_amount
                
                # Get supplier name - your model has direct supplier field (CharField)
                supplier_name = return_obj.supplier or "Unknown Supplier"
                invoice_no = return_obj.invoice_no or "N/A"
                
                report_data.append({
                    'sl': sl_number,
                    'invoice_no': invoice_no,
                    'supplier': supplier_name,
                    'total_amount': total_amount,
                    'return_amount': return_amount,
                    'date': return_obj.return_date  # FIX: Use return_date
                })
                sl_number += 1
            
            # Make sure you have this serializer
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
            
            # Get date range from request with proper defaults
            date_filter = request.GET.get('dateFilter', 'current_day')
            
            # Calculate date range based on filter
            today = timezone.now().date()
            if date_filter == 'current_day':
                start_date = today
                end_date = today
            elif date_filter == 'this_month':
                start_date = today.replace(day=1)
                end_date = today
            elif date_filter == 'lifeTime':
                # For lifetime, use a very early date
                start_date = datetime(2020, 1, 1).date()
                end_date = today
            else:
                start_date = today
                end_date = today

            print(f"=== DASHBOARD DEBUG ===")
            print(f"Date filter: {date_filter}, Range: {start_date} to {end_date}")
            print(f"Company ID: {company.id}")

            # IMPORTANT: Convert dates to datetimes for universal compatibility
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # ===== SALES CALCULATIONS =====
            # ALWAYS use __gte and __lte to avoid __date__range issues
            sales_query = Sale.objects.filter(
                company=company, 
                sale_date__gte=start_datetime,
                sale_date__lte=end_datetime
            )
            
            today_sales = sales_query.aggregate(
                total=Sum('grand_total'),
                count=Count('id'),
                total_due=Sum('due_amount')
            )

            # Sale items - use the same date range
            today_sales_quantity = SaleItem.objects.filter(
                sale__company=company,
                sale__sale_date__gte=start_datetime,
                sale__sale_date__lte=end_datetime
            ).aggregate(
                total_quantity=Sum('quantity')
            )

            # Calculate profit
            sale_items = SaleItem.objects.filter(
                sale__company=company,
                sale__sale_date__gte=start_datetime,
                sale__sale_date__lte=end_datetime
            ).select_related('product')
            
            total_profit = 0
            for item in sale_items:
                purchase_price = item.product.purchase_price if item.product and item.product.purchase_price else 0
                profit_per_item = (item.unit_price - purchase_price) * item.quantity
                total_profit += profit_per_item

            # ===== SALES RETURNS =====
            try:
                today_sales_returns = SalesReturn.objects.filter(
                    company=company,
                    return_date__gte=start_datetime,
                    return_date__lte=end_datetime
                ).aggregate(
                    total_amount=Sum('return_amount'),
                    count=Count('id')
                )
                
                # Get sales return quantity
                today_sales_return_quantity = SalesReturnItem.objects.filter(
                    sales_return__company=company,
                    sales_return__return_date__gte=start_datetime,
                    sales_return__return_date__lte=end_datetime
                ).aggregate(
                    total_quantity=Sum('quantity')
                )
            except Exception as e:
                print(f"Sales return error: {e}")
                today_sales_returns = {'total_amount': 0, 'count': 0}
                today_sales_return_quantity = {'total_quantity': 0}

            # ===== PURCHASE CALCULATIONS =====
            purchases_query = Purchase.objects.filter(
                company=company,
                purchase_date__gte=start_datetime,
                purchase_date__lte=end_datetime
            )
            
            today_purchases = purchases_query.aggregate(
                total=Sum('grand_total'),
                count=Count('id'),
                total_due=Sum('due_amount')
            )

            # Purchase items
            today_purchases_quantity = PurchaseItem.objects.filter(
                purchase__company=company,
                purchase__purchase_date__gte=start_datetime,
                purchase__purchase_date__lte=end_datetime
            ).aggregate(
                total_quantity=Sum('qty')
            )

            # ===== PURCHASE RETURNS =====
            try:
                today_purchase_returns = PurchaseReturn.objects.filter(
                    company=company,
                    return_date__gte=start_datetime,
                    return_date__lte=end_datetime
                ).aggregate(
                    total_amount=Sum('return_amount'),
                    count=Count('id')
                )
                
                today_purchase_return_quantity = PurchaseReturnItem.objects.filter(
                    purchase_return__company=company,
                    purchase_return__return_date__gte=start_datetime,
                    purchase_return__return_date__lte=end_datetime
                ).aggregate(
                    total_quantity=Sum('qty')
                )
            except Exception as e:
                print(f"Purchase return error: {e}")
                today_purchase_returns = {'total_amount': 0, 'count': 0}
                today_purchase_return_quantity = {'total_quantity': 0}

            # ===== EXPENSES =====
            today_expenses = Expense.objects.filter(
                company=company,
                expense_date__gte=start_datetime,
                expense_date__lte=end_datetime
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )

            # ===== DEBUG OUTPUT =====
            print(f"\n=== METRICS DEBUG ===")
            print(f"Sales - Total: {today_sales['total']}, Count: {today_sales['count']}, Due: {today_sales['total_due']}")
            print(f"Sales Quantity: {today_sales_quantity['total_quantity']}")
            print(f"Sales Profit: {total_profit}")

            # ===== FINANCIAL CALCULATIONS =====
            sales_total = float(today_sales['total'] or 0)
            sales_due = float(today_sales['total_due'] or 0)
            sales_returns_total = float(today_sales_returns['total_amount'] or 0)
            
            purchases_total = float(today_purchases['total'] or 0)
            purchases_due = float(today_purchases['total_due'] or 0)
            purchase_returns_total = float(today_purchase_returns['total_amount'] or 0)
            
            expenses_total = float(today_expenses['total'] or 0)

            sales_net_amount = sales_total - sales_due
            purchases_net_amount = purchases_total - purchases_due
            
            net_sales_after_returns = sales_total - sales_returns_total
            net_purchases_after_returns = purchases_total - purchase_returns_total
            
            gross_profit = float(total_profit)
            net_profit = gross_profit - expenses_total
            
            cash_inflows = sales_net_amount
            cash_outflows = purchases_net_amount + expenses_total
            operating_cash_flow = cash_inflows - cash_outflows

            profit_margin = 0
            if sales_total > 0:
                profit_margin = (gross_profit / sales_total) * 100

            # ===== STOCK ALERTS =====
            low_stock_count = Product.objects.filter(
                company=company,
                stock_qty__lte=F('alert_quantity'),
                stock_qty__gt=0
            ).count()
            
            out_of_stock_count = Product.objects.filter(
                company=company,
                stock_qty=0
            ).count()

            # ===== RECENT ACTIVITIES =====
            recent_sales = Sale.objects.filter(
                company=company
            ).select_related('customer').order_by('-sale_date')[:5]
            
            recent_sales_data = []
            for sale in recent_sales:
                sale_quantity = SaleItem.objects.filter(sale=sale).aggregate(
                    total_quantity=Sum('quantity')
                )['total_quantity'] or 0
                
                # FIXED: No .date() call here
                date_str = sale.sale_date
                if date_str:
                    # If it's a datetime, convert to date string
                    if hasattr(date_str, 'date'):
                        date_str = date_str.date().isoformat()
                    else:
                        date_str = date_str.isoformat()
                
                recent_sales_data.append({
                    'invoice_no': sale.invoice_no,
                    'customer': sale.customer.name if sale.customer else "Walk-in",
                    'amount': float(sale.grand_total or 0),
                    'due_amount': float(sale.due_amount or 0),
                    'quantity': sale_quantity,
                    'date': date_str
                })

            recent_purchases = Purchase.objects.filter(
                company=company
            ).select_related('supplier').order_by('-purchase_date')[:5]
            
            recent_purchases_data = []
            for purchase in recent_purchases:
                purchase_quantity = PurchaseItem.objects.filter(purchase=purchase).aggregate(
                    total_quantity=Sum('qty')
                )['total_quantity'] or 0
                
                # FIXED: Handle both date and datetime
                date_str = purchase.purchase_date
                if date_str:
                    if hasattr(date_str, 'date'):
                        date_str = date_str.date().isoformat()
                    else:
                        date_str = date_str.isoformat()
                
                recent_purchases_data.append({
                    'invoice_no': purchase.invoice_no,
                    'supplier': purchase.supplier.name if purchase.supplier else "Unknown",
                    'amount': float(purchase.grand_total or 0),
                    'due_amount': float(purchase.due_amount or 0),
                    'quantity': purchase_quantity,
                    'date': date_str
                })

            # ===== FINAL RESPONSE DATA =====
            dashboard_data = {
                'today_metrics': {
                    'sales': {
                        'total': sales_total,
                        'count': today_sales['count'] or 0,
                        'total_quantity': today_sales_quantity['total_quantity'] or 0,
                        'total_due': sales_due,
                        'net_total': sales_net_amount
                    },
                    'sales_returns': {
                        'total_amount': sales_returns_total,
                        'total_quantity': today_sales_return_quantity['total_quantity'] or 0,
                        'count': today_sales_returns['count'] or 0
                    },
                    'purchases': {
                        'total': purchases_total,
                        'count': today_purchases['count'] or 0,
                        'total_quantity': today_purchases_quantity['total_quantity'] or 0,
                        'total_due': purchases_due,
                        'net_total': purchases_net_amount
                    },
                    'purchase_returns': {
                        'total_amount': purchase_returns_total,
                        'total_quantity': today_purchase_return_quantity['total_quantity'] or 0,
                        'count': today_purchase_returns['count'] or 0
                    },
                    'expenses': {
                        'total': expenses_total,
                        'count': today_expenses['count'] or 0
                    }
                },
                'profit_loss': {
                    'gross_profit': gross_profit,
                    'net_profit': net_profit,
                    'profit_margin': round(profit_margin, 2)
                },
                'financial_summary': {
                    'net_sales': net_sales_after_returns,
                    'net_purchases': net_purchases_after_returns,
                    'gross_profit': gross_profit,
                    'net_profit': net_profit,
                    'operating_cash_flow': operating_cash_flow,
                    'cash_components': {
                        'cash_in': cash_inflows,
                        'cash_out_purchases': purchases_net_amount,
                        'cash_out_expenses': expenses_total
                    }
                },
                'stock_alerts': {
                    'low_stock': low_stock_count,
                    'out_of_stock': out_of_stock_count
                },
                'recent_activities': {
                    'sales': recent_sales_data,
                    'purchases': recent_purchases_data
                },
                'date_filter_info': {
                    'filter_type': date_filter,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }

            return custom_response(True, "Dashboard data fetched successfully", dashboard_data)
            
        except Exception as e:
            print(f"Dashboard error: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.handle_exception(e)