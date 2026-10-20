"""পুরনো স্টকের জন্য ব্যাচ/মেয়াদ তৈরি।

ব্যাচ শুধু নতুন ক্রয় থেকে তৈরি হয়। এই কমান্ড চালালে বর্তমান স্টক (stock_qty) পেছনের ক্রয়গুলোর সাথে মিলিয়ে —
সবচেয়ে নতুন ক্রয় আগে ধরে, কারণ পুরনো মাল আগে বিক্রি হয়ে যায় — ব্যাচ বানায়, যাতে Expiry Alerts পুরনো স্টকেও কাজ করে।

    python manage.py backfill_batches --dry-run        # শুধু দেখাও, কিছু লিখো না
    python manage.py backfill_batches                  # সব কোম্পানি
    python manage.py backfill_batches --company 3      # একটা কোম্পানি

বারবার চালালেও নিরাপদ: যে product এর ব্যাচ আগেই স্টকের সমান, তাতে কিছু বদলায় না।
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from products.models import Product
from purchases.models import ProductBatch, PurchaseItem

ZERO = Decimal('0')


class Command(BaseCommand):
    help = "বর্তমান স্টকের জন্য পুরনো ক্রয় থেকে ব্যাচ/মেয়াদ তৈরি করে (নিরাপদ, বারবার চালানো যায়)"

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, help='শুধু এই company id')
        parser.add_argument('--dry-run', action='store_true', help='কিছু না লিখে শুধু হিসাব দেখাও')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        products = Product.objects.filter(stock_qty__gt=0)
        if opts.get('company'):
            products = products.filter(company_id=opts['company'])

        made = covered_products = short_products = 0
        short_units = 0
        for p in products.iterator():
            have = ProductBatch.objects.filter(product=p).aggregate(s=Sum('qty_remaining'))['s'] or ZERO
            need = Decimal(p.stock_qty) - have
            if need <= 0:
                continue
            items = (PurchaseItem.objects
                     .filter(product=p, price__gt=0, batch__isnull=True)
                     .exclude(purchase__payment_status='cancelled')
                     .select_related('purchase')
                     .order_by('-purchase__purchase_date', '-id'))
            with transaction.atomic():
                for it in items:
                    if need <= 0:
                        break
                    take = min(need, Decimal(it.qty))
                    made += 1
                    need -= take
                    if not dry:
                        ProductBatch.objects.create(
                            company_id=p.company_id, product=p, purchase_item=it,
                            batch_no=it.batch_no, expiry_date=it.expiry_date,
                            qty_received=Decimal(it.qty), qty_remaining=take,
                            received_at=it.date_created)
            if need > 0:      # ক্রয়ের হিসাবে নেই (যেমন ওপেনিং স্টক) — মেয়াদ জানা সম্ভব নয়
                short_products += 1
                short_units += int(need)
            else:
                covered_products += 1

        tag = '[dry-run] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f"{tag}{made} টা ব্যাচ {'তৈরি হতো' if dry else 'তৈরি হলো'} — "
            f"{covered_products} টা পণ্যের স্টক পুরোপুরি ব্যাচে ধরা পড়ল।"))
        if short_products:
            self.stdout.write(
                f"{short_products} টা পণ্যের মোট {short_units} ইউনিট ক্রয়ের হিসাবে মেলেনি (ওপেনিং স্টক/হাতে বদলানো) — "
                f"এগুলোর মেয়াদ অজানা থাকবে।")
