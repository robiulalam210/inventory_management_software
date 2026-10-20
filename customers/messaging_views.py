"""Messages API — /api/messages/…   (সব কোম্পানি অনুযায়ী আলাদা)"""
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from reports.perms import user_has_perm
from reports.utils import custom_response

from . import messaging
from .models import MessageSchedule, OutboxMessage


def _admin(user):
    return bool(user.is_superuser or getattr(user, 'role', '') in ('SUPER_ADMIN', 'ADMIN'))


class _Base(APIView):
    permission_classes = [IsAuthenticated]

    def company(self, request):
        c = getattr(request.user, 'company', None)
        if c is None:
            raise ValueError('User must be associated with a company')
        return c

    def can_view(self, user):
        return _admin(user) or user_has_perm(user, 'customers', 'view')

    def can_manage(self, user):
        return _admin(user) or user_has_perm(user, 'customers', 'edit')

    def handle_exception(self, exc):
        if isinstance(exc, PermissionError):
            return custom_response(False, str(exc), None, 403)
        if isinstance(exc, (ValueError, LookupError)):
            return custom_response(False, str(exc), None, 400)
        return super().handle_exception(exc)

    def need_view(self, request):
        if not self.can_view(request.user):
            raise PermissionError('You do not have permission to view messages')

    def need_manage(self, request):
        if not self.can_manage(request.user):
            raise PermissionError('You do not have permission to manage message schedules')


def _msg_json(m):
    return {
        'id': m.id, 'kind': m.kind, 'kind_label': dict(MessageSchedule.KINDS).get(m.kind, m.kind),
        'customer_id': m.customer_id, 'name': m.recipient_name, 'phone': m.phone, 'text': m.text,
        'status': m.status, 'created_at': m.created_at.isoformat(),
        'sent_at': m.sent_at.isoformat() if m.sent_at else None,
        'schedule_name': (m.schedule.name or m.schedule.get_kind_display()) if m.schedule_id else '',
        'whatsapp_url': messaging.whatsapp_url(m.phone, m.text),
    }


def _sched_json(s):
    nxt = None
    return {
        'id': s.id, 'name': s.name, 'kind': s.kind, 'kind_label': s.get_kind_display(),
        'frequency': s.frequency, 'send_time': s.send_time.strftime('%H:%M') if hasattr(s.send_time, 'strftime') else str(s.send_time)[:5],
        'weekday': s.weekday, 'day_of_month': s.day_of_month,
        'run_date': s.run_date.isoformat() if s.run_date else None, 'enabled': s.enabled,
        'template': s.template, 'min_amount': float(s.min_amount), 'min_days': s.min_days,
        'audience': s.audience, 'recent_days': s.recent_days, 'notify_phone': s.notify_phone,
        'last_run_at': s.last_run_at.isoformat() if s.last_run_at else None,
        'default_template': messaging.DEFAULT_TEMPLATES.get(s.kind, ''),
    }


def _apply(s, d, *, creating):
    """request data → schedule ফিল্ড (ভুল হলে ValueError)"""
    if creating or 'kind' in d:
        if d.get('kind') not in dict(MessageSchedule.KINDS):
            raise ValueError('Choose what to send')
        s.kind = d['kind']
    if 'name' in d:
        s.name = (d.get('name') or '')[:100]
    if 'frequency' in d:
        if d['frequency'] not in dict(MessageSchedule.FREQUENCIES):
            raise ValueError('Choose how often')
        s.frequency = d['frequency']
    if 'send_time' in d:
        t = parse_time(str(d['send_time']))
        if t is None:
            raise ValueError('Time must look like 09:30')
        s.send_time = t
    if 'weekday' in d:
        s.weekday = None if d['weekday'] in (None, '') else max(0, min(6, int(d['weekday'])))
    if 'day_of_month' in d:
        s.day_of_month = None if d['day_of_month'] in (None, '') else max(1, min(31, int(d['day_of_month'])))
    if 'run_date' in d:
        s.run_date = None if not d['run_date'] else parse_date(str(d['run_date']))
        if d['run_date'] and s.run_date is None:
            raise ValueError('Date must look like 2026-12-31')
    if s.frequency == 'once' and not s.run_date:
        raise ValueError('Pick the date for a one-time message')
    if s.frequency == 'weekly' and s.weekday is None:
        s.weekday = 0
    if s.frequency == 'monthly' and not s.day_of_month:
        s.day_of_month = 1
    for k in ('enabled',):
        if k in d:
            setattr(s, k, bool(d[k]))
    if 'template' in d:
        s.template = (d.get('template') or '')[:1500]
    for k, cast in (('min_amount', float), ('min_days', int), ('recent_days', int)):
        if k in d and d[k] not in (None, ''):
            setattr(s, k, max(0, cast(d[k])))
    if 'audience' in d:
        if d['audience'] not in dict(MessageSchedule.AUDIENCES):
            raise ValueError('Choose who gets the offer')
        s.audience = d['audience']
    if 'notify_phone' in d:
        s.notify_phone = (d.get('notify_phone') or '')[:20]


class ScheduleListView(_Base):
    def get(self, request):
        self.need_view(request)
        rows = MessageSchedule.objects.filter(company=self.company(request))
        return custom_response(True, 'OK', [_sched_json(s) for s in rows])

    def post(self, request):
        self.need_manage(request)
        s = MessageSchedule(company=self.company(request), created_by=request.user)
        _apply(s, request.data, creating=True)
        s.last_run_at = timezone.now()      # আজকের পেরিয়ে যাওয়া সময়ে হঠাৎ চালু হবে না — পরের নির্ধারিত সময় থেকে
        s.save()
        return custom_response(True, 'Schedule saved', _sched_json(s))


class ScheduleDetailView(_Base):
    def _get(self, request, pk):
        s = MessageSchedule.objects.filter(pk=pk, company=self.company(request)).first()
        if s is None:
            raise LookupError('Schedule not found')
        return s

    def patch(self, request, pk):
        self.need_manage(request)
        s = self._get(request, pk)
        _apply(s, request.data, creating=False)
        s.save()
        return custom_response(True, 'Schedule updated', _sched_json(s))

    def delete(self, request, pk):
        self.need_manage(request)
        self._get(request, pk).delete()
        return custom_response(True, 'Schedule deleted', None)


class ScheduleRunNowView(_Base):
    """এখনই মেসেজ তৈরি করো (নির্ধারিত সময়ের অপেক্ষা না করে)"""

    def post(self, request, pk):
        self.need_manage(request)
        s = MessageSchedule.objects.filter(pk=pk, company=self.company(request)).first()
        if s is None:
            raise LookupError('Schedule not found')
        n = messaging.run_schedule(s)
        return custom_response(True, f'{n} message(s) ready to send' if n else 'Nothing to send right now', {'created': n})


class OutboxListView(_Base):
    def get(self, request):
        self.need_view(request)
        company = self.company(request)
        messaging.generate_for_company(company)          # সময় হয়ে থাকলে এখনই তৈরি হয়ে যায়
        status = request.GET.get('status', 'pending')
        qs = OutboxMessage.objects.filter(company=company).select_related('schedule')
        if status in ('pending', 'sent', 'skipped'):
            qs = qs.filter(status=status)
        try:
            limit = max(1, min(500, int(request.GET.get('limit', 200))))
        except ValueError:
            limit = 200
        counts = {k: OutboxMessage.objects.filter(company=company, status=k).count() for k in ('pending', 'sent', 'skipped')}
        return custom_response(True, 'OK', {'results': [_msg_json(m) for m in qs[:limit]], 'counts': counts})


class OutboxSummaryView(_Base):
    """শুধু কয়টা মেসেজ পাঠানোর জন্য প্রস্তুত — ড্যাশবোর্ড/অ্যাপের ব্যানারের জন্য"""

    def get(self, request):
        self.need_view(request)
        company = self.company(request)
        messaging.generate_for_company(company)
        return custom_response(True, 'OK', {'pending': OutboxMessage.objects.filter(company=company, status='pending').count()})


class OutboxMarkView(_Base):
    """POST { ids: [..], status: 'sent'|'skipped'|'pending' } — WhatsApp খুলে পাঠানোর পর 'sent' চিহ্নিত করতে"""

    def post(self, request):
        self.need_view(request)
        status = request.data.get('status')
        if status not in ('sent', 'skipped', 'pending'):
            raise ValueError('Invalid status')
        ids = [int(i) for i in (request.data.get('ids') or [])]
        qs = OutboxMessage.objects.filter(company=self.company(request), id__in=ids)
        n = qs.update(status=status, sent_at=timezone.now() if status == 'sent' else None)
        return custom_response(True, f'{n} updated', {'updated': n})
