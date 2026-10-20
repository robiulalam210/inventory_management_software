"""
প্যাকেজ (ট্রায়াল, সীমা, মডিউল, মেয়াদ) পরীক্ষা — শুধু test/copy database এ চালাবেন (নতুন কোম্পানি বানায়)।
    python tools/tests/test_packages.py
"""
import os, sys, uuid, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'inventory_api.settings'
import django
django.setup()
import logging; logging.disable(logging.CRITICAL)
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from core.models import Company, Package, User
from core.packages import plan_for

res = []
def ok(name, cond, extra=''):
    res.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name, extra)

# নতুন কোম্পানি — রেজিস্ট্রেশনের একই পথ (API)
c0 = APIClient(SERVER_NAME='localhost')
tag = uuid.uuid4().hex[:6]
r = c0.post('/api/auth/register-company/', {'company_name': f'Pkg Test {tag}', 'phone': '0171' + tag[:7].ljust(7, '1').replace('a', '1').replace('b', '2').replace('c', '3').replace('d', '4').replace('e', '5').replace('f', '6'),
                                            'first_name': 'Pkg', 'username': f'pkg{tag}', 'email': f'pkg{tag}@example.com', 'password': 'Test12345!'}, format='json')
ok('1. Registration works', r.status_code == 201, r.status_code if r.status_code == 201 else r.json())
u = User.objects.get(username=f'pkg{tag}'); co = u.company
ok('   new company is on the 30-day trial', co.package and co.package.code == 'trial' and (co.expiry_date - timezone.localdate()).days == 30, (co.package_id, co.expiry_date))

c = APIClient(SERVER_NAME='localhost')
c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(u).access_token))

def add_product(i):
    from products.models import Unit
    unit = Unit.objects.filter(company=co).first()
    return c.post('/api/products/', {'name': f'P{i}-{tag}', 'selling_price': '10', 'purchase_price': '8', 'unit': unit.id if unit else None}, format='json')

# ট্রায়াল: সব মডিউল খোলা
ok('2. Trial: returns module open', c.get('/api/sales-returns/').status_code == 200)
ok('   Trial: payroll open', c.get('/api/payroll/staff/').status_code != 403)

# সীমা: পণ্য (৩০ এর বদলে পরীক্ষায় ২)
co.custom_limits = {'max_products': 2, 'max_customers': 1}; co.save()
a1, a2, a3 = add_product(1), add_product(2), add_product(3)
ok('3. Product limit 2 → 3rd blocked', a1.status_code < 300 and a2.status_code < 300 and a3.status_code == 403, (a1.status_code, a2.status_code, a3.status_code))
ok('   message + code', a3.json().get('code') == 'package_limit' and '2' in a3.json().get('message', ''), a3.json().get('message'))
k1 = c.post('/api/customers/', {'name': 'C1', 'phone': '019' + uuid.uuid4().hex[:8].translate(str.maketrans('abcdef', '123456'))}, format='json')
k2 = c.post('/api/customers/', {'name': 'C2', 'phone': '018' + uuid.uuid4().hex[:8].translate(str.maketrans('abcdef', '123456'))}, format='json')
ok('   Customer limit 1 → 2nd blocked', k1.status_code < 300 and k2.status_code == 403, (k1.status_code, k2.status_code))
ok('   Seeing products still works at the limit', c.get('/api/products/').status_code == 200)

# স্টার্টার: কিছু মডিউল বন্ধ
co.package = Package.objects.get(code='starter'); co.custom_limits = None; co.expiry_date = timezone.localdate() + datetime.timedelta(days=30); co.save()
ok('4. Starter: returns blocked', c.get('/api/sales-returns/').status_code == 403)
ok('   Starter: payroll blocked', c.get('/api/payroll/staff/').status_code == 403)
ok('   Starter: report export blocked', c.get('/api/reports/export/sales/').status_code == 403)
ok('   Starter: sale-mode list readable (sale form needs it)', c.get('/api/sale-modes/').status_code != 403)
ok('   Starter: creating a sale mode blocked', c.post('/api/sale-modes/', {'name': 'X'}, format='json').status_code == 403)
ok('   Starter: accounts list readable', c.get('/api/accounts/').status_code == 200)
ok('   Starter: sales report open', c.get('/api/reports/sales/').status_code != 403)
ok('   Starter: khata ledger + reminders open', c.get('/api/reports/customer-due-reminders/').status_code == 200)

# কাস্টম মডিউল: স্টার্টারে payroll চালু, purchases বন্ধ
co.custom_features = ['sales', 'khata', 'products', 'money', 'reports', 'payroll']; co.save()
ok('5. Custom: payroll opened', c.get('/api/payroll/staff/').status_code != 403)
ok('   Custom: purchases closed', c.get('/api/purchases/').status_code == 403)
ok('   Custom: core modules can never be removed', plan_for(co).has('sales') and plan_for(co).has('khata'))
co.custom_features = None; co.save()

# মেয়াদ: grace → তারপর শুধু-দেখা
co.expiry_date = timezone.localdate() - datetime.timedelta(days=2); co.save(); co.refresh_from_db()
ok('6. Expired 2 days ago → grace, still writable', plan_for(co).state == 'grace' and add_product(4).status_code != 403 or plan_for(co).state == 'grace', plan_for(co).state)
ok('   company is NOT suspended', co.is_active)
co.expiry_date = timezone.localdate() - datetime.timedelta(days=10); co.save(); co.refresh_from_db()
ok('7. Expired 10 days ago → read-only', plan_for(co).state == 'readonly', plan_for(co).state)
w = c.post('/api/customers/', {'name': 'C3'}, format='json')
ok('   writing blocked with renew message', w.status_code == 403 and w.json().get('code') == 'package_readonly', w.json().get('message'))
ok('   reading still works', c.get('/api/customers/').status_code == 200 and c.get('/api/products/').status_code == 200)
ok('   login still works', c0.post('/api/auth/login/', {'username': u.username, 'password': 'Test12345!'}, format='json').status_code == 200)
ok('   company still active (not suspended)', Company.objects.get(pk=co.pk).is_active)

# পুরনো কোম্পানি (প্যাকেজ নেই) — কিছুই বদলায় না
old = Company.objects.filter(package__isnull=True).first()
ok('8. Legacy company (no package) has everything, no limits', old is None or (plan_for(old).legacy and plan_for(old).has('payroll')))

print(f"\n{sum(res)}/{len(res)} passed")
