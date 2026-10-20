"""
GET /api/reports/warranty/  — ওয়ারেন্টি চেক

বিক্রি হওয়া যেসব পণ্যের ওয়ারেন্টি আছে (SaleItem.warranty_months > 0), তাদের মেয়াদ কবে শেষ।
মেয়াদ = বিক্রির তারিখ + বিক্রির দিনের ওয়ারেন্টি মাস (পরে পণ্যের ওয়ারেন্টি বদলালেও পুরনো বিক্রি বদলায় না)।

Filter (ঐচ্ছিক):
    q       ইনভয়েস নং, কাস্টমারের নাম/ফোন, বা পণ্যের নাম/SKU
    status  active | expiring (৩০ দিনের মধ্যে শেষ) | expired | all (ডিফল্ট all)
অনুমতি: sales.view
"""
import calendar

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.utils import custom_response

from .perms import user_has_perm

MAX_ROWS = 300
EXPIRING_DAYS = 30


def add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


class WarrantyCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_has_perm(request.user, 'sales', 'view'):
            return custom_response(False, 'You do not have permission to view sales.', None, 403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return custom_response(False, 'User must be associated with a company.', None, 400)
        from sales.models import SaleItem

        qs = (SaleItem.objects.filter(sale__company=company, warranty_months__gt=0)
              .select_related('sale', 'sale__customer', 'product').order_by('-sale__sale_date', '-id'))
        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(sale__invoice_no__icontains=q) | Q(sale__customer__name__icontains=q)
                           | Q(sale__customer__phone__icontains=q) | Q(sale__customer_name__icontains=q)
                           | Q(product__name__icontains=q) | Q(product__sku__icontains=q))
        status = (request.GET.get('status') or 'all').lower()
        today = timezone.localdate()
        rows, counts = [], {'active': 0, 'expiring': 0, 'expired': 0}
        for it in qs[:2000]:
            sold = timezone.localtime(it.sale.sale_date).date() if timezone.is_aware(it.sale.sale_date) else it.sale.sale_date.date()
            until = add_months(sold, it.warranty_months)
            left = (until - today).days
            st = 'expired' if left < 0 else ('expiring' if left <= EXPIRING_DAYS else 'active')
            counts[st] += 1
            if status != 'all' and st != status and not (status == 'active' and st == 'expiring'):
                continue
            if len(rows) >= MAX_ROWS:
                continue
            c = it.sale.customer
            rows.append({
                'sale_id': it.sale_id, 'invoice_no': it.sale.invoice_no, 'sale_date': sold.isoformat(),
                'customer_name': (c.name if c else it.sale.customer_name) or 'Walk-in Customer',
                'customer_phone': (c.phone if c else '') or '',
                'product_id': it.product_id, 'product_name': it.product.name, 'sku': it.product.sku or '',
                'quantity': float(it.quantity), 'warranty_months': it.warranty_months,
                'warranty_until': until.isoformat(), 'days_left': left, 'status': st,
            })
        return custom_response(True, 'Warranty list', {'rows': rows, 'counts': counts, 'expiring_days': EXPIRING_DAYS})
