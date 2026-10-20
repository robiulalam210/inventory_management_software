"""
শাখা অনুযায়ী স্টক (ধাপ ২) — এক জায়গায় সব নিয়ম।

মূল কৌশল: Product.stock_qty (মোট) আগের সব কোড যেভাবে বদলাত সেভাবেই বদলায়। Product save হলে
(signal) মোট কতটা বদলাল সেটা বের করে সেই পরিমাণ "ঠিক শাখার" BranchStock এ বসানো হয়। তাই বিক্রি,
ক্রয়, ফেরত, স্টক ঠিক করা, অনলাইন অর্ডার — প্রতিটা জায়গায় আলাদা করে লিখতে হয়নি।

"ঠিক শাখা" কোনটা (প্রথমটা যা পাওয়া যায়):
  1. কোড নিজে বলে দিলে (stock_branch(...) / @branch_of) — যেমন পুরনো বিক্রি মুছলে সেই বিক্রির শাখা
  2. এই অনুরোধে বাছা শাখা (core/branches.py — স্টাফের নিজের শাখা বা মালিকের বাছাই)
  3. প্রধান শাখা

শাখা-স্টক চালু থাকে তখন থেকে যখন কোম্পানির প্রধান শাখা তৈরি হয় (দ্বিতীয় শাখা খোলার সময়)।
এক শাখার দোকানে এখানে কিছুই হয় না।
"""
import contextvars
import functools
from contextlib import contextmanager

from django.db.models import F

_UNSET = object()
_ctx = contextvars.ContextVar('dk_stock_branch', default=_UNSET)


def _models():
    from .models import Branch, BranchStock
    return Branch, BranchStock


def main_branch_id(company_id):
    Branch, _ = _models()
    return Branch.objects.filter(company_id=company_id, is_main=True).values_list('id', flat=True).first()


def tracking(company_id):
    """শাখা-স্টক চালু কি না (প্রধান শাখা আছে মানে চালু)"""
    return bool(company_id) and main_branch_id(company_id) is not None


@contextmanager
def stock_branch(branch_id):
    """এই ব্লকের ভেতরের স্টক বদল এই শাখার (None = প্রধান শাখা)"""
    token = _ctx.set(branch_id)
    try:
        yield
    finally:
        _ctx.reset(token)


def branch_of(getter):
    """method decorator: @branch_of(lambda self: self.sale.branch_id)"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                bid = getter(self)
            except Exception:  # noqa: BLE001
                bid = None
            with stock_branch(bid):
                return fn(self, *args, **kwargs)
        return wrapper
    return deco


def target_branch(company_id):
    """এই মুহূর্তের স্টক বদল কোন শাখার"""
    main = main_branch_id(company_id)
    if main is None:
        return None
    v = _ctx.get()
    if v is not _UNSET:
        return v or main
    from core.branches import branch_state
    st = branch_state()
    if st.get('on') and st.get('id'):
        return st['id']
    return main


def apply_delta(company_id, product_id, delta, branch_id=None):
    """একটা শাখার স্টক delta পরিমাণ বাড়ানো/কমানো"""
    if not delta or not company_id:
        return
    bid = branch_id or target_branch(company_id)
    if bid is None:
        return
    _, BranchStock = _models()
    updated = BranchStock.objects.filter(branch_id=bid, product_id=product_id).update(qty=F('qty') + int(delta))
    if not updated:
        BranchStock.objects.create(branch_id=bid, product_id=product_id, qty=int(delta))


def qty_in(branch_id, product_id):
    _, BranchStock = _models()
    return BranchStock.objects.filter(branch_id=branch_id, product_id=product_id).values_list('qty', flat=True).first() or 0


def init_company(company, main):
    """প্রধান শাখা তৈরির মুহূর্তে: এখনকার সব স্টক প্রধান শাখায় (একবারই)"""
    from products.models import Product
    _, BranchStock = _models()
    if BranchStock.objects.filter(branch__company=company).exists():
        return
    rows = [BranchStock(branch=main, product_id=pid, qty=int(q or 0))
            for pid, q in Product.objects.filter(company=company).values_list('id', 'stock_qty')]
    BranchStock.objects.bulk_create(rows, batch_size=500)


def check_sale_stock(product, qty, branch_id):
    """বিক্রির আগে: শাখায় যথেষ্ট আছে কি না। না থাকলে বার্তা, থাকলে None"""
    company_id = getattr(product, 'company_id', None)
    main = main_branch_id(company_id)
    if main is None:
        return None
    bid = branch_id or main
    have = qty_in(bid, product.id)
    if have >= qty:
        return None
    Branch, _ = _models()
    name = Branch.objects.filter(pk=bid).values_list('name', flat=True).first() or ''
    unit = product.unit.name if getattr(product, 'unit', None) else 'units'
    return (f'Not enough {product.name} in {name}: {have} {unit} here. '
            f'Send stock from another branch first (Branches → Send stock).')


# ───────── Product save → শাখায় বসানো (signal) ─────────

def _pre_save(sender, instance, **kwargs):
    instance._dk_old_stock = None
    if instance.pk and tracking(instance.company_id):
        instance._dk_old_stock = sender.objects.filter(pk=instance.pk).values_list('stock_qty', flat=True).first()


def _post_save(sender, instance, created, **kwargs):
    if not tracking(instance.company_id):
        return
    new = int(instance.stock_qty or 0)
    old = 0 if created else getattr(instance, '_dk_old_stock', None)
    if old is None:
        return
    delta = new - int(old)
    if delta:
        apply_delta(instance.company_id, instance.pk, delta)


def connect():
    from django.db.models.signals import post_save, pre_save
    from products.models import Product
    pre_save.connect(_pre_save, sender=Product, dispatch_uid='dk_branch_stock_pre')
    post_save.connect(_post_save, sender=Product, dispatch_uid='dk_branch_stock_post')
