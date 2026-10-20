"""
শাখা (ধাপ ১) পরীক্ষা — শুধু test/copy database এ চালাবেন (শাখা, স্টাফ, বিক্রি বানায়; শেষে শাখাগুলো মুছে দেয়)।
    python tools/tests/test_branches.py <দোকানের admin username>
"""
import os, sys, uuid, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'inventory_api.settings'
import django
django.setup()
import logging; logging.disable(logging.CRITICAL)
from decimal import Decimal as D
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import User, Company, Package
from branch_warehouse.models import Branch
from accounts.models import Account
from products.models import Product
from sales.models import Sale
from money_receipts.models import MoneyReceipt
from expenses.models import Expense

res = []
def ok(name, cond, extra=''):
    res.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name, extra)

def client(user, branch=None):
    c = APIClient(SERVER_NAME='localhost')
    h = {'HTTP_AUTHORIZATION': 'Bearer ' + str(RefreshToken.for_user(user).access_token)}
    if branch is not None:
        h['HTTP_X_BRANCH'] = str(branch)
    c.credentials(**h)
    return c

owner = User.objects.get(username=sys.argv[1] if len(sys.argv) > 1 else 'rahim')
co = owner.company
assert not Branch.objects.filter(company=co).exists(), 'এই দোকানে আগে থেকেই শাখা আছে — অন্য দোকানে চালান'
today = datetime.date.today().isoformat()
acc = Account.objects.filter(company=co, ac_type='Cash').first()
prod = Product.objects.filter(company=co, is_active=True).first()

def sale(c, user, paid=100):
    body = {'type': 'normal_sale', 'sale_date': today, 'sale_by': str(user.id),
            'items': [{'product_id': prod.id, 'quantity': 1, 'unit_price': 100, 'discount': 0, 'discount_type': 'fixed'}],
            'customer_type': 'walk_in', 'with_money_receipt': 'Yes' if paid else 'No', 'paid_amount': paid,
            'payment_method': 'Cash', 'account_id': acc.id if acc else None,
            'overall_vat_type': 'fixed', 'vat': 0, 'overall_service_type': 'fixed', 'service_charge': 0,
            'overall_delivery_type': 'fixed', 'delivery_charge': 0, 'overall_discount_type': 'fixed', 'overall_discount': 0}
    r = c.post('/api/sales/', body, format='json')
    assert r.status_code < 300, r.json()
    return Sale.objects.get(id=r.json()['data']['id'])

# ── ১. সাধারণ দোকান: কিছুই বদলায় না
o = client(owner)
r = o.get('/api/branches/').json()['data']
ok('1. No branches → branch mode off', r['enabled'] is False and r['branches'] == [])
s0 = sale(o, owner)
ok('   sale without branches has no branch', s0.branch_id is None)

# ── ২. প্যাকেজের সীমা: ট্রায়ালে ১ শাখা
tco = Company.objects.filter(package__code='trial').exclude(pk=co.pk).first()
if tco:
    tu = User.objects.filter(company=tco, role='ADMIN').first()
    r = client(tu).post('/api/branches/', {'name': 'X'}, format='json')
    ok('2. Trial package (1 branch) → adding a branch blocked', r.status_code == 403 and r.json().get('code') == 'package_limit', r.json().get('message'))

# ── ৩. দ্বিতীয় শাখা → প্রধান শাখা নিজে তৈরি
r = o.post('/api/branches/', {'name': 'Uttara', 'address': 'Sector 7'}, format='json')
ok('3. Add "Uttara" → 201', r.status_code == 201, r.status_code)
main = Branch.objects.get(company=co, is_main=True); utt = Branch.objects.get(company=co, name='Uttara')
r = o.get('/api/branches/').json()['data']
ok('   main branch created automatically, mode on', r['enabled'] and len(r['branches']) == 2 and r['branches'][0]['is_main'])
ok('   same name blocked', o.post('/api/branches/', {'name': 'uttara'}, format='json').status_code == 400)
mir = Branch.objects.get(pk=o.post('/api/branches/', {'name': 'Mirpur'}, format='json').json()['data']['branch']['id'])
# শাখা-স্টক (ধাপ ২): নতুন শাখায় মাল না থাকলে বিক্রি আটকায় — তাই আগে প্রধান শাখা থেকে কিছু পাঠাই
for _b in (utt, mir):
    o.post('/api/branches/transfers/', {'from_branch': main.id, 'to_branch': _b.id,
                                        'items': [{'product_id': prod.id, 'qty': 3}]}, format='json')

# ── ৪. স্টাফ শাখায় বসানো
staff = User(company=co, username='br' + uuid.uuid4().hex[:6], role='MANAGER', is_active=True); staff.set_password('Test12345!'); staff.save()
r = o.patch(f'/api/users/{staff.id}/', {'branch': utt.id}, format='json')
staff.refresh_from_db()
ok('4. Admin assigns staff to Uttara', r.status_code == 200 and staff.branch_id == utt.id, r.json().get('message'))
st = client(staff)
s1 = sale(st, staff, paid=100)
ok('   staff sale → Uttara', s1.branch_id == utt.id, s1.branch_id)
rc = MoneyReceipt.objects.filter(sale=s1).first()
ok('   its money receipt → Uttara too', rc is None or rc.branch_id == utt.id, rc and rc.branch_id)
ok('   staff can\'t switch branch', st.post('/api/branches/current/', {'branch': mir.id}, format='json').status_code == 403)
ok('   staff X-Branch header ignored', sale(client(staff, mir.id), staff).branch_id == utt.id)
lst = st.get('/api/sales/?page_size=200').json()
rows = lst.get('data', lst); rows = rows.get('results', rows) if isinstance(rows, dict) else rows
ids = {x['id'] for x in rows}
ok('   staff list shows only Uttara sales', s1.id in ids and s0.id not in ids, len(ids))
ok('   staff can\'t open a main-branch sale', st.get(f'/api/sales/{s0.id}/').status_code == 404)

# ── ৫. মালিক শাখা বাছেন
s2 = sale(client(owner, mir.id), owner)
ok('5. Owner with Mirpur picked → sale in Mirpur', s2.branch_id == mir.id)
s3 = sale(o, owner)
ok('   owner "all branches" → sale in main (empty)', s3.branch_id is None)
def ids_for(b):
    j = client(owner, b).get('/api/sales/?page_size=500').json(); rr = j.get('data', j); rr = rr.get('results', rr) if isinstance(rr, dict) else rr
    return {x['id'] for x in rr}
mi = ids_for(main.id)
ok('   main branch list includes old (empty) entries, not Uttara', s0.id in mi and s3.id in mi and s1.id not in mi)
ok('   all-branches list has everything', {s0.id, s1.id, s2.id, s3.id} <= ids_for('all'))
ok('   owner can still open a Uttara sale while Mirpur picked', client(owner, mir.id).get(f'/api/sales/{s1.id}/').status_code == 200)

# ── ৬. রিপোর্ট
def sales_total(b):
    j = client(owner, b).get(f'/api/reports/sales/?start_date={today}&end_date={today}').json()
    d = j.get('data') or {}
    return d.get('summary', {}).get('total_sales') if isinstance(d, dict) else None
t_all, t_mir = sales_total('all'), sales_total(mir.id)
ok('6. Sales report: Mirpur total = Mirpur sales', t_mir is not None and D(str(t_mir)) == s2.grand_total, (t_all, t_mir))
ok('   all > Mirpur', t_all is not None and D(str(t_all)) > D(str(t_mir)))
d1 = client(owner, utt.id).get('/api/reports/dashboard/').status_code
ok('   dashboard with a branch works', d1 == 200, d1)

# ── ৭. বন্ধ করা
ok('7. Main branch can\'t be closed', o.patch(f'/api/branches/{main.id}/', {'is_active': False}, format='json').status_code == 400)
ok('   branch with staff can\'t be closed', o.patch(f'/api/branches/{utt.id}/', {'is_active': False}, format='json').status_code == 400)
ok('   empty branch can be closed', o.patch(f'/api/branches/{mir.id}/', {'is_active': False}, format='json').status_code == 200)

# পরিষ্কার
staff.branch = None; staff.is_active = False; staff.save()
for m in (Sale, MoneyReceipt, Expense):
    m.objects.filter(company=co, branch__in=[main, utt, mir]).update(branch=None)
from branch_warehouse.models import BranchStock, StockTransfer
StockTransfer.objects.filter(company=co).delete()
BranchStock.objects.filter(branch__company=co).delete()
Branch.objects.filter(company=co).delete()
print(f"\n{sum(res)}/{len(res)} passed")
