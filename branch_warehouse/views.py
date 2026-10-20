"""
শাখার API — /api/branches/

  GET    /api/branches/            → শাখার তালিকা (প্রতিটার আজকের বিক্রি, স্টাফ সংখ্যা) + এখন কোনটা বাছা
  POST   /api/branches/            → নতুন শাখা (প্রথমবার হলে প্রধান শাখাও তৈরি হয়) — প্যাকেজের max_branches সীমা মানে
  PATCH  /api/branches/<id>/       → নাম/ঠিকানা/ফোন বদলানো, বন্ধ/চালু
  POST   /api/branches/current/    → {branch: id | "all"} — ওপরে কোন শাখার হিসাব দেখবেন (web session এ থাকে)

শাখা বানানো/বদলানো শুধু দোকানের Admin পারেন; বাছাই সবাই (শাখায় বসানো স্টাফ নিজের শাখার বাইরে যেতে পারেন না)।
"""
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.branches import SESSION_KEY, branch_state, ensure_main
from .models import Branch


def _ok(data=None, message='', status=200):
    return Response({'status': True, 'success': True, 'message': message, 'data': data}, status=status)


def _err(message, status=400, errors=None):
    return Response({'status': False, 'success': False, 'message': message, 'errors': errors or {}}, status=status)


def _is_admin(user):
    return bool(user.is_superuser or getattr(user, 'role', '') in ('ADMIN', 'SUPER_ADMIN'))


def _row(b, sales=None, staff=None):
    return {'id': b.id, 'name': b.name, 'code': b.code, 'address': b.address, 'phone': b.phone,
            'is_main': b.is_main, 'is_active': b.is_active,
            'today_sales': str(sales or 0), 'staff_count': staff or 0}


class BranchListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if company is None:
            return _ok({'branches': [], 'enabled': False})
        from sales.models import Sale
        from core.models import User
        today = timezone.localdate()
        branches = list(Branch.objects.filter(company=company))
        main = next((b for b in branches if b.is_main), None)
        sales_by = dict(Sale.objects.filter(company=company, sale_date__date=today)
                        .values_list('branch').annotate(t=Sum('grand_total')).values_list('branch', 't'))
        if main is not None and None in sales_by:                       # শাখা ফাঁকা = প্রধান শাখা
            sales_by[main.id] = (sales_by.get(main.id) or 0) + sales_by.pop(None)
        staff_by = dict(User.objects.filter(company=company, is_active=True, branch__isnull=False)
                        .values_list('branch').annotate(n=Count('id')).values_list('branch', 'n'))
        st = branch_state(request)
        return _ok({
            'branches': [_row(b, sales_by.get(b.id), staff_by.get(b.id)) for b in branches],
            'enabled': sum(1 for b in branches if b.is_active) >= 2,
            'current': st.get('id'), 'locked': st.get('locked', False),
            'can_manage': _is_admin(request.user),
        })

    def post(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if company is None or not _is_admin(user):
            return _err('Only the shop admin can add branches.', 403)
        name = (request.data.get('name') or '').strip()
        if not name:
            return _err('Enter the branch name.', errors={'name': 'Enter the branch name.'})
        try:
            with transaction.atomic():
                main = ensure_main(company)
                if Branch.objects.filter(company=company, name__iexact=name).exists():
                    return _err('A branch with this name already exists.', errors={'name': 'A branch with this name already exists.'})
                b = Branch.objects.create(company=company, name=name[:120],
                                          address=(request.data.get('address') or '').strip()[:255],
                                          phone=(request.data.get('phone') or '').strip()[:20],
                                          code=(request.data.get('code') or '').strip()[:20])
        except IntegrityError:
            return _err('A branch with this name already exists.', errors={'name': 'A branch with this name already exists.'})
        return _ok({'branch': _row(b), 'main': _row(main)}, 'Branch added.', 201)


class BranchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        user = request.user
        company = getattr(user, 'company', None)
        if company is None or not _is_admin(user):
            return _err('Only the shop admin can change branches.', 403)
        b = Branch.objects.filter(company=company, pk=pk).first()
        if b is None:
            return _err('Branch not found.', 404)
        d = request.data
        if 'name' in d:
            name = (d.get('name') or '').strip()
            if not name:
                return _err('Enter the branch name.', errors={'name': 'Enter the branch name.'})
            if Branch.objects.filter(company=company, name__iexact=name).exclude(pk=b.pk).exists():
                return _err('A branch with this name already exists.', errors={'name': 'A branch with this name already exists.'})
            b.name = name[:120]
        for f, n in (('address', 255), ('phone', 20), ('code', 20)):
            if f in d:
                setattr(b, f, (d.get(f) or '').strip()[:n])
        if 'is_active' in d:
            active = bool(d.get('is_active'))
            if not active and b.is_main:
                return _err("The main branch can't be closed.")
            if not active:
                from core.models import User
                if User.objects.filter(company=company, branch=b, is_active=True).exists():
                    return _err('Move this branch\'s staff to another branch first.')
            b.is_active = active
        b.save()
        return _ok({'branch': _row(b)}, 'Branch saved.')


class BranchCurrentView(APIView):
    """ওপরের শাখা বাছাই — web এ session এ থাকে, পরের সব পেজ/রিপোর্ট সেই শাখার"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if company is None:
            return _err('No company.', 400)
        if getattr(user, 'branch_id', None):
            return _err('You work in one branch; you can\'t switch.', 403)
        val = request.data.get('branch')
        if val in (None, '', 'all'):
            request.session.pop(SESSION_KEY, None)
            return _ok({'current': None})
        b = Branch.objects.filter(company=company, pk=val, is_active=True).first()
        if b is None:
            return _err('Branch not found.', 404)
        request.session[SESSION_KEY] = b.id
        return _ok({'current': b.id})


# ───────────────────────── শাখা অনুযায়ী স্টক ও মাল পাঠানো (ধাপ ২) ─────────────────────────

def _can_move_stock(user):
    return bool(_is_admin(user) or (hasattr(user, 'has_permission') and user.has_permission('products', 'edit')))


class BranchStockView(APIView):
    """
    GET /api/branches/stock/                → {branches: [...], stock: {product_id: {branch_id: qty}}}
    GET /api/branches/stock/?product=<id>   → শুধু একটা পণ্যের (অ্যাপের পণ্য পাতার জন্য)
    শাখা-স্টক চালু না থাকলে enabled=false।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import BranchStock
        from .stock import tracking
        company = getattr(request.user, 'company', None)
        if company is None or not tracking(company.id):
            return _ok({'enabled': False, 'branches': [], 'stock': {}})
        branches = list(Branch.objects.filter(company=company).values('id', 'name', 'is_main', 'is_active'))
        qs = BranchStock.objects.filter(branch__company=company)
        pid = request.GET.get('product')
        if pid:
            qs = qs.filter(product_id=pid)
        stock = {}
        for p, b, q in qs.values_list('product_id', 'branch_id', 'qty'):
            stock.setdefault(str(p), {})[str(b)] = q
        return _ok({'enabled': True, 'branches': branches, 'stock': stock})


class StockTransferView(APIView):
    """
    GET  /api/branches/transfers/   → শেষ ১০০টা পাঠানো
    POST /api/branches/transfers/   {from_branch, to_branch, note, items: [{product_id, qty}]}
         → যেখান থেকে কমে, যেখানে যোগ হয়। মোট স্টক (Product.stock_qty) একটুও বদলায় না।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import StockTransfer
        company = getattr(request.user, 'company', None)
        if company is None:
            return _ok([])
        rows = []
        for t in (StockTransfer.objects.filter(company=company)
                  .select_related('from_branch', 'to_branch', 'created_by').prefetch_related('items__product')[:100]):
            rows.append({
                'id': t.id, 'transfer_no': t.transfer_no, 'date': t.created_at.isoformat(),
                'from_branch': t.from_branch_id, 'from_name': t.from_branch.name,
                'to_branch': t.to_branch_id, 'to_name': t.to_branch.name, 'note': t.note,
                'by': (t.created_by.get_full_name() or t.created_by.username) if t.created_by else '',
                'items': [{'product_id': i.product_id, 'name': i.product.name, 'qty': i.qty} for i in t.items.all()],
            })
        return _ok(rows)

    def post(self, request):
        from django.db.models import F
        from products.models import Product
        from .models import BranchStock, StockTransfer, StockTransferItem
        from .stock import tracking
        user = request.user
        company = getattr(user, 'company', None)
        if company is None or not _can_move_stock(user):
            return _err('You do not have permission to move stock.', 403)
        if not tracking(company.id):
            return _err('Add a second branch first.')
        d = request.data
        src = Branch.objects.filter(company=company, pk=d.get('from_branch') or 0, is_active=True).first()
        dst = Branch.objects.filter(company=company, pk=d.get('to_branch') or 0, is_active=True).first()
        if src is None or dst is None:
            return _err('Choose both branches.', errors={'branch': 'Choose both branches.'})
        if src.pk == dst.pk:
            return _err('Choose two different branches.', errors={'branch': 'Choose two different branches.'})
        # স্টাফ নিজের শাখা থেকেই পাঠাতে পারেন
        own = getattr(user, 'branch_id', None)
        if own and src.pk != own:
            return _err('You can only send stock from your own branch.', 403)
        lines = {}
        for it in (d.get('items') or []):
            try:
                pid, qty = int(it.get('product_id')), int(float(it.get('qty') or 0))
            except (TypeError, ValueError):
                continue
            if qty > 0:
                lines[pid] = lines.get(pid, 0) + qty
        if not lines:
            return _err('Add at least one product with a quantity.', errors={'items': 'Add at least one product.'})
        products = {p.id: p for p in Product.objects.filter(company=company, pk__in=lines.keys())}
        if len(products) != len(lines):
            return _err('Some products were not found.')
        with transaction.atomic():
            have = dict(BranchStock.objects.select_for_update()
                        .filter(branch=src, product_id__in=lines.keys()).values_list('product_id', 'qty'))
            short = [f'{products[p].name} ({have.get(p, 0)} {src.name})' for p, q in lines.items() if have.get(p, 0) < q]
            if short:
                return _err(f'Not enough stock in {src.name}: ' + ', '.join(short),
                            errors={'items': 'Not enough stock: ' + ', '.join(short)})
            n = StockTransfer.objects.filter(company=company).count() + 1
            t = StockTransfer.objects.create(company=company, from_branch=src, to_branch=dst, created_by=user,
                                             note=(d.get('note') or '').strip()[:255], transfer_no=f'ST-{n:04d}')
            for p, q in lines.items():
                StockTransferItem.objects.create(transfer=t, product_id=p, qty=q)
                BranchStock.objects.filter(branch=src, product_id=p).update(qty=F('qty') - q)
                if not BranchStock.objects.filter(branch=dst, product_id=p).update(qty=F('qty') + q):
                    BranchStock.objects.create(branch=dst, product_id=p, qty=q)
        return _ok({'id': t.id, 'transfer_no': t.transfer_no, 'items': len(lines)},
                   f'{len(lines)} product(s) sent to {dst.name}.', 201)
