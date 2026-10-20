"""
বাকি খাতা — বিক্রি ছাড়া বাকি (CustomerDue) এর API

    GET    /api/customer-dues/?customer=<id>     একজনের সব এন্ট্রি (নতুন আগে)
    POST   /api/customer-dues/                   নতুন: {customer_id, amount, kind: credit|opening, entry_date: YYYY-MM-DD, note}
    DELETE /api/customer-dues/<id>/              মোছা — শুধু যদি এর কোনো অংশ এখনো শোধ না হয়ে থাকে

অনুমতি: দেখা = customers.view, যোগ = customers.create, মোছা = customers.delete
টাকা নেওয়া এখানে হয় না — শোধ হয় Money Receipt দিয়ে (money_receipts/models.py → _apply_to_manual_dues)।
"""
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.utils import custom_response
from reports.perms import user_has_perm

from .models import Customer, CustomerDue


def _row(d):
    return {
        'id': d.id, 'entry_no': d.entry_no, 'kind': d.kind, 'kind_label': d.get_kind_display(),
        'customer_id': d.customer_id, 'customer_name': d.customer.name if d.customer_id else '',
        'amount': float(d.amount), 'paid_amount': float(d.paid_amount), 'due_amount': float(d.due_amount),
        'entry_date': timezone.localtime(d.entry_date).isoformat() if timezone.is_aware(d.entry_date) else d.entry_date.isoformat(),
        'note': d.note, 'created_by': (d.created_by.get_full_name() or d.created_by.username) if d.created_by_id else '',
        'can_delete': d.paid_amount <= 0,
    }


class CustomerDueListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_has_perm(request.user, 'customers', 'view'):
            return custom_response(False, 'You do not have permission to view customers.', None, 403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return custom_response(False, 'User must be associated with a company.', None, 400)
        qs = CustomerDue.objects.filter(company=company).select_related('customer', 'created_by').order_by('-entry_date', '-id')
        cid = request.GET.get('customer')
        if cid:
            qs = qs.filter(customer_id=cid)
        rows = [_row(d) for d in qs[:500]]
        return custom_response(True, f'{len(rows)} entries', rows)

    def post(self, request):
        if not user_has_perm(request.user, 'customers', 'create'):
            return custom_response(False, 'You do not have permission to add dues.', None, 403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return custom_response(False, 'User must be associated with a company.', None, 400)
        data = request.data
        errors = {}
        customer = Customer.objects.filter(company=company, pk=data.get('customer_id') or 0).first()
        if customer is None:
            errors['customer_id'] = ['Choose the customer.']
        try:
            amount = Decimal(str(data.get('amount') or '0')).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            amount = Decimal('0')
        if amount <= 0:
            errors['amount'] = ['Enter an amount greater than 0.']
        kind = data.get('kind') or CustomerDue.KIND_CREDIT
        if kind not in dict(CustomerDue.KIND_CHOICES):
            errors['kind'] = ['Unknown kind.']
        when = timezone.now()
        raw = (data.get('entry_date') or '').strip()
        if raw:
            try:
                day = datetime.strptime(raw[:10], '%Y-%m-%d').date()
                if day > timezone.localdate():
                    errors['entry_date'] = ['The date cannot be in the future.']
                elif day != timezone.localdate():
                    when = timezone.make_aware(datetime.combine(day, time(12, 0)))
            except ValueError:
                errors['entry_date'] = ['Use the date format YYYY-MM-DD.']
        if errors:
            return custom_response(False, next(iter(errors.values()))[0], errors, 400)
        with transaction.atomic():
            d = CustomerDue(company=company, customer=customer, kind=kind, amount=amount, entry_date=when,
                            note=(data.get('note') or '').strip()[:255], created_by=request.user)
            d.full_clean(exclude=['entry_no'])
            d.save()
        return custom_response(True, f'{d.entry_no} saved.', _row(d), 201)


class CustomerDueDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not user_has_perm(request.user, 'customers', 'delete'):
            return custom_response(False, 'You do not have permission to delete dues.', None, 403)
        company = getattr(request.user, 'company', None)
        d = CustomerDue.objects.filter(company=company, pk=pk).first()
        if d is None:
            return custom_response(False, 'Entry not found.', None, 404)
        if d.paid_amount > 0:
            return custom_response(False, 'Part of this due has already been paid. Cancel that money receipt first.', None, 400)
        no = d.entry_no
        d.delete()
        return custom_response(True, f'{no} deleted.', None)
