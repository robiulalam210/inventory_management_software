"""
শাখা (Branch) — একই দোকানের একাধিক জায়গা।

নিয়ম (core/branches.py তে বিস্তারিত):
  • শাখা ১টা (বা একটাও না) থাকলে সফটওয়্যারে শাখার কিছুই দেখায় না — সাধারণ দোকান আগের মতোই চলে।
  • দ্বিতীয় শাখা খুললে নিজে থেকে "প্রধান শাখা" তৈরি হয়; আগের সব এন্ট্রি (শাখা ফাঁকা) প্রধান শাখার ধরা হয়।
  • মোছা যায় না, শুধু বন্ধ (is_active=False) করা যায় — পুরনো হিসাব যেন হারিয়ে না যায়।
  • স্টক এখনো পুরো দোকানের এক জায়গায় (শাখা অনুযায়ী আলাদা স্টক পরের ধাপে)।
"""
from django.db import models


class Branch(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_main', 'name']
        unique_together = [('company', 'name')]

    def __str__(self):
        return self.name


class BranchStock(models.Model):
    """
    শাখা অনুযায়ী স্টক (ধাপ ২)। Product.stock_qty = সব শাখার যোগফল — আগের মতোই থাকে,
    তাই পুরনো রিপোর্ট/অ্যাপ বদলায় না। এখানে শুধু "কোন শাখায় কত" আলাদা রাখা হয়।
    দ্বিতীয় শাখা খোলার সময় এখনকার সব স্টক প্রধান শাখায় বসে (branch_warehouse/stock.py)।
    """
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='branch_stocks')
    qty = models.IntegerField(default=0)

    class Meta:
        unique_together = [('branch', 'product')]

    def __str__(self):
        return f'{self.product_id} @ {self.branch_id}: {self.qty}'


class StockTransfer(models.Model):
    """এক শাখা থেকে আরেক শাখায় মাল পাঠানো — মোট স্টক বদলায় না। ভুল হলে উল্টো দিকে আরেকটা পাঠানো।"""
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='stock_transfers')
    transfer_no = models.CharField(max_length=20, blank=True, default='')
    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='transfers_out')
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='transfers_in')
    note = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='+')
    qty = models.PositiveIntegerField()
