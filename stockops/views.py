"""অ্যাপের Stock Adjustment / Stocktake / Day Close API। সব জবাব { status, message, data }; সব কোম্পানি অনুযায়ী আলাদা।"""
import math
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from products.models import Product
from reports.perms import user_has_perm
from reports.utils import custom_response

from .models import (DayClose, DayCloseLine, StockAdjustment, Stocktake, StocktakeLine)

ZERO = Decimal('0')


def _f(v):
    return float(v or 0)


def _is_admin(user):
    return bool(user.is_superuser or getattr(user, 'role', '') in ('SUPER_ADMIN', 'ADMIN'))


def _user_name(u):
    if not u:
        return ''
    full = (u.get_full_name() or '').strip() if hasattr(u, 'get_full_name') else ''
    return full or u.get_username()


class StockBaseView(APIView):
    permission_classes = [IsAuthenticated]
    module = 'products'

    def company(self, request):
        c = getattr(request.user, 'company', None)
        if c is None:
            raise ValueError('User must be associated with a company')
        return c

    def need(self, request, action='view', module=None):
        if not user_has_perm(request.user, module or self.module, action):
            raise PermissionError(f"You do not have permission to {action} this")

    def handle_exception(self, exc):
        if isinstance(exc, PermissionError):
            return custom_response(False, str(exc), None, 403)
        if isinstance(exc, (ValueError, LookupError)):
            return custom_response(False, str(exc), None, 400)
        return super().handle_exception(exc)


# ───────────────────────── Stock Adjustment ─────────────────────────

def _apply_adjustment(company, user, product, new_qty, reason, note, stocktake=None):
    """product এর stock_qty কে new_qty তে নিয়ে যায় এবং হিসাব রাখে। transaction.atomic এর ভেতরে ডাকতে হবে।"""
    product = Product.objects.select_for_update().get(pk=product.pk, company=company)
    before = int(product.stock_qty)
    new_qty = int(new_qty)
    if new_qty < 0:
        raise ValueError(f"Stock can't go below zero ({product.name} has {before}).")
    change = new_qty - before
    if change == 0:
        return None
    product.stock_qty = new_qty
    product.save(update_fields=['stock_qty', 'updated_at'])
    if change < 0:
        try:
            from purchases.batches import consume_for_adjustment
            consume_for_adjustment(product.pk, -change)
        except Exception:
            pass
    adj = StockAdjustment.objects.create(
        company=company, product=product, qty_before=before, qty_after=new_qty, change=change,
        value_change=Decimal(change) * (product.purchase_price or ZERO), reason=reason,
        note=(note or '')[:300], stocktake=stocktake, created_by=user)
    adj.number = f"ADJ-{adj.pk:06d}"
    adj.save(update_fields=['number'])
    return adj


def _adj_json(a):
    return {
        'id': a.id, 'number': a.number, 'product_id': a.product_id, 'product_name': a.product.name,
        'sku': a.product.sku or '', 'qty_before': a.qty_before, 'qty_after': a.qty_after, 'change': a.change,
        'value_change': _f(a.value_change), 'reason': a.reason, 'reason_label': a.get_reason_display(),
        'note': a.note, 'stocktake_number': a.stocktake.number if a.stocktake_id else '',
        'created_by': _user_name(a.created_by), 'created_at': a.created_at.isoformat(),
    }


class StockAdjustmentView(StockBaseView):
    def get(self, request):
        self.need(request, 'view')
        company = self.company(request)
        qs = StockAdjustment.objects.filter(company=company).select_related('product', 'created_by', 'stocktake')
        q = (request.GET.get('q') or '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q) | Q(number__icontains=q))
        reason = request.GET.get('reason')
        if reason:
            qs = qs.filter(reason=reason)
        try:
            page = max(1, int(request.GET.get('page', 1)))
            size = min(100, max(1, int(request.GET.get('page_size', 30))))
        except ValueError:
            page, size = 1, 30
        count = qs.count()
        loss = gain = ZERO
        for v in qs.values_list('value_change', flat=True):
            if v < 0:
                loss += -v
            else:
                gain += v
        rows = qs[(page - 1) * size: page * size]
        return custom_response(True, 'OK', {
            'results': [_adj_json(a) for a in rows], 'count': count, 'page': page,
            'total_pages': max(1, math.ceil(count / size)),
            'totals': {'net_value': _f(gain - loss), 'loss_value': _f(loss), 'gain_value': _f(gain)},
        })

    @transaction.atomic
    def post(self, request):
        self.need(request, 'edit')
        company = self.company(request)
        d = request.data
        try:
            product = Product.objects.get(pk=int(d.get('product_id')), company=company)
        except (TypeError, ValueError, Product.DoesNotExist):
            raise ValueError('Product not found')
        reason = d.get('reason') or 'other'
        if reason not in dict(StockAdjustment.REASONS) or reason == 'count':
            raise ValueError('Choose a valid reason')
        cur = int(product.stock_qty)
        if d.get('new_qty') not in (None, ''):
            new_qty = int(d['new_qty'])
        elif d.get('change') not in (None, ''):
            new_qty = cur + int(d['change'])
        else:
            raise ValueError('Give the new quantity or the change')
        adj = _apply_adjustment(company, request.user, product, new_qty, reason, d.get('note'))
        if adj is None:
            raise ValueError('Quantity is already the same — nothing to change')
        sign = f"{adj.change:+d}"
        return custom_response(True, f"{product.name}: {adj.qty_before} → {adj.qty_after} ({sign})", _adj_json(adj))


# ───────────────────────── Stocktake ─────────────────────────

def _summary(lines):
    total = counted = differing = short_q = over_q = 0
    short_v = over_v = ZERO
    for ln in lines:
        total += 1
        if ln.counted_qty is None:
            continue
        counted += 1
        var = ln.counted_qty - ln.system_qty
        if var:
            differing += 1
        if var < 0:
            short_q += -var
            short_v += Decimal(-var) * ln.unit_cost
        elif var > 0:
            over_q += var
            over_v += Decimal(var) * ln.unit_cost
    return {'total': total, 'counted': counted, 'uncounted': total - counted, 'differing': differing,
            'short_qty': short_q, 'over_qty': over_q, 'short_value': _f(short_v), 'over_value': _f(over_v),
            'net_value': _f(over_v - short_v)}


def _head_json(s, lines=None):
    lines = list(s.lines.all()) if lines is None else lines
    return {
        'id': s.id, 'number': s.number, 'title': s.title, 'note': s.note, 'status': s.status,
        'status_label': s.get_status_display(), 'category_name': s.category.name if s.category_id else '',
        'created_by': _user_name(s.created_by), 'created_at': s.created_at.isoformat(),
        'applied_at': s.applied_at.isoformat() if s.applied_at else None, 'summary': _summary(lines),
    }


def _mine(request, view, pk):
    try:
        return Stocktake.objects.select_related('category', 'created_by').get(pk=pk, company=view.company(request))
    except Stocktake.DoesNotExist:
        raise LookupError('Stocktake not found')


class StocktakeListView(StockBaseView):
    def get(self, request):
        self.need(request, 'view')
        company = self.company(request)
        out = []
        for s in Stocktake.objects.filter(company=company).select_related('category', 'created_by').prefetch_related('lines')[:60]:
            out.append(_head_json(s))
        return custom_response(True, 'OK', out)

    @transaction.atomic
    def post(self, request):
        self.need(request, 'edit')
        company = self.company(request)
        d = request.data
        products = Product.objects.filter(company=company, is_active=True)
        cat = None
        if d.get('category_id') not in (None, ''):
            from products.models import Category
            cat = Category.objects.filter(pk=d['category_id'], company=company).first()
            if cat is None:
                raise ValueError('Category not found')
            products = products.filter(category=cat)
        products = list(products)
        if not products:
            raise ValueError('No products to count')
        n = Stocktake.objects.filter(company=company).count() + 1
        s = Stocktake.objects.create(company=company, number=f"CNT-{n:04d}", title=(d.get('title') or '')[:150],
                                     note=(d.get('note') or '')[:300], category=cat, created_by=request.user)
        StocktakeLine.objects.bulk_create([
            StocktakeLine(stocktake=s, product=p, system_qty=int(p.stock_qty), unit_cost=p.purchase_price or ZERO)
            for p in products])
        return custom_response(True, f"Stocktake {s.number} started with {len(products)} products", _head_json(s))


class StocktakeDetailView(StockBaseView):
    def get(self, request, pk):
        self.need(request, 'view')
        s = _mine(request, self, pk)
        lines = list(s.lines.select_related('product', 'product__category'))
        data = _head_json(s, lines)
        data['lines'] = [{
            'id': ln.id, 'product_id': ln.product_id, 'name': ln.product.name, 'sku': ln.product.sku or '',
            'category': ln.product.category.name if ln.product.category_id else '',
            'system_qty': ln.system_qty, 'counted_qty': ln.counted_qty, 'unit_cost': _f(ln.unit_cost),
            'system_now': int(ln.product.stock_qty), 'moved': int(ln.product.stock_qty) != ln.system_qty,
            'applied_change': ln.applied_change,
        } for ln in lines]
        return custom_response(True, 'OK', data)


class StocktakeCountView(StockBaseView):
    @transaction.atomic
    def post(self, request, pk):
        self.need(request, 'edit')
        s = _mine(request, self, pk)
        if s.status != 'draft':
            raise ValueError('This stocktake is already closed')
        rows = request.data.get('rows') or []
        by_id = {ln.id: ln for ln in s.lines.all()}
        for r in rows:
            ln = by_id.get(int(r.get('line_id', 0)))
            if ln is None:
                continue
            v = r.get('counted_qty')
            ln.counted_qty = None if v in (None, '') else max(0, int(v))
            ln.save(update_fields=['counted_qty'])
        return custom_response(True, 'Saved', _summary(by_id.values()))


class StocktakeApplyView(StockBaseView):
    @transaction.atomic
    def post(self, request, pk):
        self.need(request, 'edit')
        company = self.company(request)
        s = _mine(request, self, pk)
        if s.status != 'draft':
            raise ValueError('This stocktake is already closed')
        changed = 0
        for ln in s.lines.select_related('product'):
            if ln.counted_qty is None:
                continue
            adj = _apply_adjustment(company, request.user, ln.product, ln.counted_qty, 'count',
                                    f"Stocktake {s.number}", stocktake=s)
            ln.applied_change = adj.change if adj else 0
            ln.save(update_fields=['applied_change'])
            if adj:
                changed += 1
        s.status = 'applied'
        s.applied_at = timezone.now()
        s.save(update_fields=['status', 'applied_at'])
        return custom_response(True, f"Stocktake applied — {changed} product(s) corrected", None)


class StocktakeCancelView(StockBaseView):
    def post(self, request, pk):
        self.need(request, 'edit')
        s = _mine(request, self, pk)
        if s.status != 'draft':
            raise ValueError('Only an in-progress stocktake can be cancelled')
        s.status = 'cancelled'
        s.save(update_fields=['status'])
        return custom_response(True, 'Stocktake cancelled', None)


# ───────────────────────── Day Close ─────────────────────────

def _day_summary(company, day):
    from accounts.models import Account
    from expenses.models import Expense
    from income.models import Income
    from money_receipts.models import MoneyReceipt
    from purchases.models import Purchase
    from returns.models import SalesReturn
    from sales.models import Sale
    from transactions.models import Transaction
    from django.db.models import Count, Sum

    def agg(qs, field, due=None):
        r = qs.aggregate(n=Count('id'), t=Sum(field))
        out = {'count': r['n'] or 0, 'total': _f(r['t'])}
        if due:
            out['due'] = _f(qs.aggregate(d=Sum(due))['d'])
        return out

    sales_qs = Sale.objects.filter(company=company, sale_date__date=day).exclude(payment_status='cancelled')
    ret_qs = SalesReturn.objects.filter(company=company, return_date=day).exclude(status='rejected')
    pur_qs = Purchase.objects.filter(company=company, purchase_date=day).exclude(payment_status='cancelled')
    sales = agg(sales_qs, 'grand_total', 'due_amount')
    returns = agg(ret_qs, 'return_amount')
    purchases = agg(pur_qs, 'grand_total')
    expenses = agg(Expense.objects.filter(company=company, expense_date=day), 'amount')
    income = agg(Income.objects.filter(company=company, income_date=day), 'amount')
    receipts = agg(MoneyReceipt.objects.filter(company=company, payment_date__date=day), 'amount')

    accounts = []
    total_expected = ZERO
    for a in Account.objects.filter(company=company, is_active=True).order_by('id'):
        tx = Transaction.objects.filter(company=company, account=a, status='completed')
        on_day = tx.filter(transaction_date__date=day)
        money_in = on_day.filter(transaction_type='credit').aggregate(t=Sum('amount'))['t'] or ZERO
        money_out = on_day.filter(transaction_type='debit').aggregate(t=Sum('amount'))['t'] or ZERO
        after = tx.filter(transaction_date__date__gt=day)
        a_cr = after.filter(transaction_type='credit').aggregate(t=Sum('amount'))['t'] or ZERO
        a_db = after.filter(transaction_type='debit').aggregate(t=Sum('amount'))['t'] or ZERO
        expected = (a.balance or ZERO) - a_cr + a_db      # দিনের শেষের balance = এখনকার balance থেকে পরের লেনদেন বাদ
        total_expected += expected
        accounts.append({'account_id': a.id, 'name': a.name, 'type': a.ac_type, 'money_in': _f(money_in),
                         'money_out': _f(money_out), 'expected': _f(expected)})
    return {
        'date': str(day), 'sales': sales, 'returns': returns, 'purchases': purchases, 'expenses': expenses,
        'income': income, 'receipts': receipts, 'net_sales': _f(Decimal(str(sales['total'])) - Decimal(str(returns['total']))),
        'accounts': accounts, 'total_expected': _f(total_expected),
    }


def _close_json(dc):
    return {
        'id': dc.id, 'date': str(dc.date), 'note': dc.note, 'total_expected': _f(dc.total_expected),
        'total_counted': _f(dc.total_counted), 'difference': _f(dc.difference),
        'closed_by': _user_name(dc.closed_by), 'closed_at': dc.closed_at.isoformat(),
        'lines': [{'account_id': ln.account_id, 'name': ln.name, 'type': ln.type, 'money_in': _f(ln.money_in),
                   'money_out': _f(ln.money_out), 'expected': _f(ln.expected), 'counted': _f(ln.counted),
                   'difference': _f(ln.difference)} for ln in dc.lines.all()],
    }


def _parse_day(text):
    from django.utils.dateparse import parse_date
    day = parse_date(text or '') or timezone.localdate()
    if day > timezone.localdate():
        raise ValueError("You can't close a future day")
    return day


class DayCloseSummaryView(StockBaseView):
    module = 'accounts'

    def get(self, request):
        self.need(request, 'view')
        company = self.company(request)
        day = _parse_day(request.GET.get('date'))
        dc = DayClose.objects.filter(company=company, date=day).prefetch_related('lines').select_related('closed_by').first()
        return custom_response(True, 'OK', {
            'summary': _day_summary(company, day),
            'closed': _close_json(dc) if dc else None,
            'can_close': dc is None and user_has_perm(request.user, 'accounts', 'edit'),
            'can_reopen': dc is not None and _is_admin(request.user),
        })


class DayCloseListView(StockBaseView):
    module = 'accounts'

    def get(self, request):
        self.need(request, 'view')
        company = self.company(request)
        try:
            size = min(100, max(1, int(request.GET.get('page_size', 14))))
        except ValueError:
            size = 14
        rows = DayClose.objects.filter(company=company).select_related('closed_by')[:size]
        return custom_response(True, 'OK', {'results': [{
            'id': d.id, 'date': str(d.date), 'total_expected': _f(d.total_expected),
            'total_counted': _f(d.total_counted), 'difference': _f(d.difference),
            'closed_by': _user_name(d.closed_by), 'closed_at': d.closed_at.isoformat(), 'note': d.note,
        } for d in rows]})

    @transaction.atomic
    def post(self, request):
        self.need(request, 'edit')
        company = self.company(request)
        day = _parse_day(request.data.get('date'))
        if DayClose.objects.filter(company=company, date=day).exists():
            raise ValueError('This day is already closed')
        counts = request.data.get('counts') or {}
        summary = _day_summary(company, day)
        dc = DayClose.objects.create(company=company, date=day, note=(request.data.get('note') or '')[:300],
                                     closed_by=request.user)
        total_exp = total_cnt = ZERO
        for a in summary['accounts']:
            exp = Decimal(str(a['expected']))
            raw = counts.get(str(a['account_id']), counts.get(a['account_id']))
            try:
                cnt = Decimal(str(raw)) if raw not in (None, '') else exp
            except Exception:
                raise ValueError(f"Invalid amount for {a['name']}")
            total_exp += exp
            total_cnt += cnt
            DayCloseLine.objects.create(day_close=dc, account_id=a['account_id'], name=a['name'], type=a['type'],
                                        money_in=a['money_in'], money_out=a['money_out'], expected=exp,
                                        counted=cnt, difference=cnt - exp)
        dc.total_expected, dc.total_counted, dc.difference = total_exp, total_cnt, total_cnt - total_exp
        dc.save(update_fields=['total_expected', 'total_counted', 'difference'])
        return custom_response(True, f"{day} closed", _close_json(dc))


class DayCloseDetailView(StockBaseView):
    module = 'accounts'

    def delete(self, request, pk):
        company = self.company(request)
        if not _is_admin(request.user):
            raise PermissionError('Only an admin can reopen a day')
        dc = DayClose.objects.filter(pk=pk, company=company).first()
        if dc is None:
            raise LookupError('Day close not found')
        dc.delete()
        return custom_response(True, 'Day reopened', None)
