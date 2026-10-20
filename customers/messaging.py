"""নির্ধারিত সময়ে মেসেজ তৈরি (due reminder / stock alert / daily summary / offer)।

WhatsApp নিজে থেকে পাঠানো যায় না — তাই সময় হলে এখানে মেসেজগুলো OutboxMessage হিসেবে তৈরি হয় ("পাঠানোর জন্য প্রস্তুত"),
দোকানি এক ট্যাপে WhatsApp খুলে পাঠান। তৈরি হয় দুইভাবে:
  • কেউ Messages পেজ / ড্যাশবোর্ড / অ্যাপ খুললে (generate_for_company) — cron লাগে না
  • চাইলে cron এ:  python manage.py generate_messages   (কেউ না খুললেও সময়মতো তৈরি থাকে)
"""
import calendar
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

from django.db.models import Count, F, Max, Min, Q, Sum
from django.utils import timezone

from reports.reminder_utils import DEFAULT_TEMPLATE, MAX_INVOICES_IN_MESSAGE, money, normalize_phone, render_message

MAX_OFFER_RECIPIENTS = 500

DEFAULT_TEMPLATES = {
    'due_reminder': DEFAULT_TEMPLATE,
    'offer': 'আসসালামু আলাইকুম {name}, {shop} থেকে বিশেষ অফার! বিস্তারিত জানতে যোগাযোগ করুন: {phone}। ধন্যবাদ।',
    'stock_alert': '{shop} — স্টক সতর্কতা ({date}):\n{body}',
    'daily_summary': '{shop} — আজকের সারাংশ ({date}):\n{body}',
}


def whatsapp_url(phone, text):
    return f'https://wa.me/{phone}?text={quote(text)}' if phone else f'https://wa.me/?text={quote(text)}'


# ───────────── কখন চলবে ─────────────

def latest_occurrence(s, now=None):
    """schedule এর সবচেয়ে সাম্প্রতিক নির্ধারিত সময় (এখন বা তার আগে), না থাকলে None। সময় local timezone এ।"""
    now = timezone.localtime(now or timezone.now())
    tz = now.tzinfo
    t = s.send_time
    if isinstance(t, str):
        h, m = (t.split(':') + ['0'])[:2]
        t = datetime(2000, 1, 1, int(h), int(m)).time()

    def at(d):
        return timezone.make_aware(datetime.combine(d, t), tz) if timezone.is_naive(datetime.combine(d, t)) else datetime.combine(d, t)

    today = now.date()
    if s.frequency == 'daily':
        cand = at(today)
        return cand if cand <= now else at(today - timedelta(days=1))
    if s.frequency == 'weekly':
        wd = 0 if s.weekday is None else s.weekday
        d = today - timedelta(days=(today.weekday() - wd) % 7)
        cand = at(d)
        return cand if cand <= now else at(d - timedelta(days=7))
    if s.frequency == 'monthly':
        dom = s.day_of_month or 1

        def month_date(y, mth):
            return datetime(y, mth, min(dom, calendar.monthrange(y, mth)[1])).date()
        cand = at(month_date(today.year, today.month))
        if cand <= now:
            return cand
        y, mth = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        return at(month_date(y, mth))
    if s.frequency == 'once':
        if not s.run_date:
            return None
        cand = at(s.run_date)
        return cand if cand <= now else None
    return None


def is_due(s, now=None):
    if not s.enabled:
        return False
    occ = latest_occurrence(s, now)
    if occ is None:
        return False
    return s.last_run_at is None or occ > timezone.localtime(s.last_run_at)


# ───────────── মেসেজ বানানো ─────────────

def _due_rows(company, s):
    """Customers পেজের "Owes you" এর সাথে হুবহু এক হিসাব (reports/reminder_views.py)"""
    from customers.models import Customer
    from sales.models import Sale

    min_amount = Decimal(str(s.min_amount or 0))
    due_sale = Q(due_amount__gt=0)
    grouped = {
        g['customer']: g
        for g in (Sale.objects.filter(company=company, customer__isnull=False, customer__is_active=True)
                  .values('customer')
                  .annotate(grand=Sum('grand_total'), paid=Sum('paid_amount'),
                            oldest=Min('sale_date', filter=due_sale))
                  )
    }
    # বাকি খাতার বিক্রি-ছাড়া বাকি — reminder_views.py এর একই নিয়ম
    from customers.models import manual_due_totals, CustomerDue
    manual = {cid: max(Decimal('0'), a - p) for cid, (a, p) in manual_due_totals(company).items()}
    for cid, m in manual.items():
        if m > 0:
            g = grouped.setdefault(cid, {'customer': cid, 'grand': Decimal('0'), 'paid': Decimal('0'), 'oldest': None})
            first = (CustomerDue.objects.filter(company=company, customer_id=cid, paid_amount__lt=F('amount'))
                     .order_by('entry_date').values_list('entry_date', flat=True).first())
            if first and (g['oldest'] is None or first < g['oldest']):
                g['oldest'] = first
    grouped = {cid: g for cid, g in grouped.items() if (g['grand'] or 0) - (g['paid'] or 0) + manual.get(cid, 0) > 0}
    customers = {c.id: c for c in Customer.objects.filter(company=company, id__in=list(grouped.keys()))}
    invoices = {}
    for r in (Sale.objects.filter(company=company, customer_id__in=list(grouped.keys()), due_amount__gt=0)
              .order_by('sale_date', 'id').values('customer_id', 'invoice_no', 'due_amount')):
        invoices.setdefault(r['customer_id'], []).append(r)
    today = timezone.localdate()
    for cid, g in grouped.items():
        c = customers.get(cid)
        if c is None:
            continue
        net = max(Decimal('0'), (g['grand'] or 0) - (g['paid'] or 0) + manual.get(cid, 0) - (c.advance_balance or 0))
        if net <= 0 or net <= min_amount:
            continue
        oldest = timezone.localtime(g['oldest']).date() if g['oldest'] else None
        days = (today - oldest).days if oldest else 0
        if days < (s.min_days or 0):
            continue
        inv = invoices.get(cid, [])
        inv_text = ', '.join(f"{(i['invoice_no'] or '#')} (৳{money(i['due_amount'])})" for i in inv[:MAX_INVOICES_IN_MESSAGE])
        if len(inv) > MAX_INVOICES_IN_MESSAGE:
            inv_text += f' ও আরও {len(inv) - MAX_INVOICES_IN_MESSAGE}টি'
        yield c, net, inv_text, days


def _owner_phone(company, s):
    return normalize_phone(s.notify_phone) or normalize_phone(company.phone) or ''


def _stock_body(company):
    from products.models import Product
    from purchases.models import ProductBatch
    from django.db.models import F

    lines = []
    low = list(Product.objects.filter(company=company, is_active=True, stock_qty__lte=F('alert_quantity'))
               .order_by('stock_qty', 'name')[:15])
    total_low = Product.objects.filter(company=company, is_active=True, stock_qty__lte=F('alert_quantity')).count()
    if total_low:
        lines.append(f'⚠ স্টক কম/শেষ: {total_low}টি পণ্য')
        for p in low:
            lines.append(f'• {p.name}: {"শেষ" if p.stock_qty == 0 else p.stock_qty}')
        if total_low > len(low):
            lines.append(f'  …আরও {total_low - len(low)}টি')
    today = timezone.localdate()
    soon = today + timedelta(days=30)
    batches = list(ProductBatch.objects.filter(company=company, qty_remaining__gt=0, expiry_date__isnull=False,
                                               expiry_date__lte=soon).select_related('product').order_by('expiry_date')[:10])
    if batches:
        exp = sum(1 for b in batches if b.expiry_date < today)
        lines.append(f'⏳ মেয়াদ: {len(batches)}টি ব্যাচ ({exp}টির মেয়াদ শেষ)')
        for b in batches:
            left = (b.expiry_date - today).days
            when = f'{-left} দিন আগে শেষ' if left < 0 else ('আজ শেষ' if left == 0 else f'{left} দিন বাকি')
            lines.append(f'• {b.product.name}: {b.expiry_date} ({when})')
    return '\n'.join(lines)


def _summary_body(company):
    from expenses.models import Expense
    from purchases.models import Purchase
    from sales.models import Sale

    today = timezone.localdate()
    s_qs = Sale.objects.filter(company=company, sale_date__date=today).exclude(payment_status='cancelled')
    s = s_qs.aggregate(n=Count('id'), t=Sum('grand_total'), p=Sum('paid_amount'))
    pur = Purchase.objects.filter(company=company, purchase_date=today).exclude(payment_status='cancelled') \
        .aggregate(t=Sum('grand_total'))['t'] or 0
    exp = Expense.objects.filter(company=company, expense_date=today).aggregate(t=Sum('amount'))['t'] or 0
    due = Sale.objects.filter(company=company, customer__isnull=False, due_amount__gt=0) \
        .aggregate(t=Sum('due_amount'))['t'] or 0
    return '\n'.join([
        f"🧾 বিক্রি: {s['n'] or 0}টি ইনভয়েস, ৳{money(s['t'])}",
        f"💵 আদায়: ৳{money(s['p'])}",
        f"🛒 ক্রয়: ৳{money(pur)}",
        f"💸 খরচ: ৳{money(exp)}",
        f"📒 মোট বাকি (কাস্টমারদের কাছে): ৳{money(due)}",
    ])


def build_messages(company, s):
    """schedule অনুযায়ী মেসেজের তালিকা: [{customer, name, phone, text}, ...]"""
    from customers.models import Customer
    from sales.models import Sale

    shop = company.name or 'আমাদের দোকান'
    shop_phone = company.phone or ''
    template = (s.template or '').strip() or DEFAULT_TEMPLATES.get(s.kind, '')
    out = []

    if s.kind == 'due_reminder':
        for c, net, inv_text, days in _due_rows(company, s):
            text = render_message(template, name=c.name or '', amount=net, shop=shop, phone=shop_phone,
                                  invoices=inv_text, days=days)
            out.append({'customer': c, 'name': c.name or '', 'phone': normalize_phone(c.phone) or '', 'text': text})

    elif s.kind == 'offer':
        cust = Customer.objects.filter(company=company, is_active=True).exclude(phone__isnull=True).exclude(phone='')
        if s.audience == 'with_due':
            cust = cust.filter(id__in=Sale.objects.filter(company=company, due_amount__gt=0).values('customer_id'))
        elif s.audience == 'recent':
            since = timezone.now() - timedelta(days=s.recent_days or 30)
            cust = cust.filter(id__in=Sale.objects.filter(company=company, sale_date__gte=since).values('customer_id'))
        for c in cust.order_by('name')[:MAX_OFFER_RECIPIENTS]:
            phone = normalize_phone(c.phone)
            if not phone:
                continue
            text = template.replace('{name}', c.name or '').replace('{shop}', shop).replace('{phone}', shop_phone)
            out.append({'customer': c, 'name': c.name or '', 'phone': phone, 'text': text.strip()})

    elif s.kind in ('stock_alert', 'daily_summary'):
        body = _stock_body(company) if s.kind == 'stock_alert' else _summary_body(company)
        if body:
            text = template.replace('{shop}', shop).replace('{date}', str(timezone.localdate())).replace('{body}', body)
            out.append({'customer': None, 'name': 'Owner', 'phone': _owner_phone(company, s), 'text': text.strip()})
    return out


def run_schedule(s, *, now=None):
    """একটা schedule চালিয়ে OutboxMessage তৈরি করে। ফেরত: তৈরি হওয়া মেসেজের সংখ্যা।
    একই customer এর জন্য এই schedule এর pending মেসেজ থাকলে নতুন বানায় না (জমে যাওয়া ঠেকাতে)।"""
    from customers.models import OutboxMessage

    company = s.company
    made = 0
    pending_customers = set(OutboxMessage.objects.filter(schedule=s, status='pending', customer__isnull=False)
                            .values_list('customer_id', flat=True))
    pending_owner = OutboxMessage.objects.filter(schedule=s, status='pending', customer__isnull=True).exists()
    rows = []
    for m in build_messages(company, s):
        if m['customer'] is not None and m['customer'].id in pending_customers:
            continue
        if m['customer'] is None and pending_owner:
            continue
        rows.append(OutboxMessage(company=company, schedule=s, kind=s.kind, customer=m['customer'],
                                  recipient_name=m['name'][:120], phone=m['phone'], text=m['text']))
    if rows:
        OutboxMessage.objects.bulk_create(rows)
        made = len(rows)
    s.last_run_at = now or timezone.now()
    if s.frequency == 'once':
        s.enabled = False
    s.save(update_fields=['last_run_at', 'enabled'])
    return made


def generate_for_company(company):
    """সময় হয়ে যাওয়া schedule গুলো চালায়। ফেরত: নতুন তৈরি মেসেজ সংখ্যা।"""
    from customers.models import MessageSchedule

    total = 0
    for s in MessageSchedule.objects.filter(company=company, enabled=True).select_related('company'):
        if is_due(s):
            try:
                total += run_schedule(s)
            except Exception:       # একটা schedule এর ভুল বাকিগুলো আটকাবে না
                import logging
                logging.getLogger(__name__).exception('Message schedule %s failed', s.pk)
    return total
