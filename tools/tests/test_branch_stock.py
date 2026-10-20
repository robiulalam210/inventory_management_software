"""
শাখা অনুযায়ী স্টক (ধাপ ২) পরীক্ষা — শুধু test/copy database এ (শাখা, বিক্রি, ক্রয় বানায়; শেষে শাখাগুলো মুছে দেয়)।
    python tools/tests/test_branch_stock.py <দোকানের admin username>
মূল শর্ত প্রতি ধাপে মেলানো হয়: প্রতিটা পণ্যের সব শাখার স্টকের যোগফল == মোট স্টক (Product.stock_qty)
"""
import os, sys, uuid, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'inventory_api.settings'
import django
django.setup()
import logging; logging.disable(logging.CRITICAL)
from django.db.models import Sum
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import User
from branch_warehouse.models import Branch, BranchStock, StockTransfer
from accounts.models import Account
from products.models import Product
from suppliers.models import Supplier
from sales.models import Sale
from purchases.models import Purchase
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
    c.credentials(**h); return c

owner = User.objects.get(username=sys.argv[1] if len(sys.argv) > 1 else 'rahim')
co = owner.company
assert not Branch.objects.filter(company=co).exists(), 'এই দোকানে আগে থেকেই শাখা আছে — অন্য দোকানে চালান'
acc = Account.objects.filter(company=co, ac_type='Cash').first()
prod = Product.objects.filter(company=co, is_active=True, stock_qty__gte=20).first()
assert prod, 'কমপক্ষে ২০টা স্টক আছে এমন একটা পণ্য লাগবে'
sup = Supplier.objects.filter(company=co).first() or Supplier.objects.create(company=co, name='Test Supplier', phone='01' + uuid.uuid4().hex[:9].translate(str.maketrans('abcdef', '123456')))
today = datetime.date.today().isoformat()

def invariant():
    bad = []
    for p in Product.objects.filter(company=co):
        s = BranchStock.objects.filter(product=p).aggregate(t=Sum('qty'))['t'] or 0
        if s != p.stock_qty: bad.append((p.id, s, p.stock_qty))
    return bad

def in_branch(b):
    return BranchStock.objects.filter(branch=b, product=prod).values_list('qty', flat=True).first() or 0

def sale(c, user, qty):
    prod.refresh_from_db()
    body = {'type': 'normal_sale', 'sale_date': today, 'sale_by': str(user.id),
            'items': [{'product_id': prod.id, 'quantity': qty, 'unit_price': 10, 'discount': 0, 'discount_type': 'fixed'}],
            'customer_type': 'walk_in', 'with_money_receipt': 'Yes', 'paid_amount': 10 * qty, 'payment_method': 'Cash',
            'account_id': acc.id, 'overall_vat_type': 'fixed', 'vat': 0, 'overall_service_type': 'fixed', 'service_charge': 0,
            'overall_delivery_type': 'fixed', 'delivery_charge': 0, 'overall_discount_type': 'fixed', 'overall_discount': 0}
    return c.post('/api/sales/', body, format='json')

o = client(owner)
# ── ১. এক শাখার দোকান: কিছুই না
r = sale(o, owner, 1)
ok('1. Single-branch shop: sale works as before', r.status_code < 300, r.status_code)
ok('   no branch stock rows created', not BranchStock.objects.filter(branch__company=co).exists())
ok('   branch stock API says off', o.get('/api/branches/stock/').json()['data']['enabled'] is False)

# ── ২. দ্বিতীয় শাখা → সব স্টক প্রধান শাখায়
o.post('/api/branches/', {'name': 'Uttara'}, format='json')
main = Branch.objects.get(company=co, is_main=True); utt = Branch.objects.get(company=co, name='Uttara')
prod.refresh_from_db(); total0 = prod.stock_qty
ok('2. On 2nd branch, all stock goes to the main branch', in_branch(main) == total0 and in_branch(utt) == 0, (in_branch(main), total0))
ok('   every product: branches add up to total', not invariant(), invariant()[:3])

# ── ৩. উত্তরায় মাল নেই → উত্তরার স্টাফ বিক্রি করতে পারে না
staff = User(company=co, username='bs' + uuid.uuid4().hex[:6], role='MANAGER', is_active=True, branch=utt)
staff.set_password('Test12345!'); staff.save()
st = client(staff)
r = sale(st, staff, 2)
msg = str(r.json())
ok('3. Uttara has 0 → staff sale blocked', r.status_code >= 400 and 'Uttara' in msg, msg[:160])
prod.refresh_from_db()
ok('   total stock unchanged by the failed sale', prod.stock_qty == total0)

# ── ৪. প্রধান → উত্তরা ৫টা পাঠানো
r = o.post('/api/branches/transfers/', {'from_branch': main.id, 'to_branch': utt.id,
                                        'items': [{'product_id': prod.id, 'qty': 5}], 'note': 'test'}, format='json')
prod.refresh_from_db()
ok('4. Transfer 5 main → Uttara', r.status_code == 201 and in_branch(utt) == 5 and in_branch(main) == total0 - 5, r.json().get('message'))
ok('   total stock unchanged by transfer', prod.stock_qty == total0)
ok('   too much is refused', o.post('/api/branches/transfers/', {'from_branch': utt.id, 'to_branch': main.id,
                                     'items': [{'product_id': prod.id, 'qty': 99}]}, format='json').status_code == 400)
ok('   staff can\'t send from another branch', st.post('/api/branches/transfers/', {'from_branch': main.id, 'to_branch': utt.id,
                                     'items': [{'product_id': prod.id, 'qty': 1}]}, format='json').status_code == 403)

# ── ৫. উত্তরার স্টাফ ২টা বিক্রি
r = sale(st, staff, 2)
prod.refresh_from_db()
ok('5. Staff sells 2 in Uttara → Uttara 3, main untouched', r.status_code < 300 and in_branch(utt) == 3 and in_branch(main) == total0 - 5,
   (r.status_code, in_branch(utt), in_branch(main)))
ok('   total stock -2', prod.stock_qty == total0 - 2)
ok('   branches add up to total', not invariant(), invariant()[:3])

# ── ৬. মালিক উত্তরা বেছে ক্রয় → উত্তরায় যোগ
pr = None
if sup:
    body = {'instant_pay': False, 'supplier': str(sup.id), 'purchase_date': today,
            'purchase_items': [{'product_id': str(prod.id), 'qty': 4, 'price': 5, 'discount': 0, 'discount_type': 'fixed'}],
            'overall_discount': 0, 'overall_discount_type': 'fixed', 'overall_service_charge': 0, 'overall_service_charge_type': 'fixed',
            'overall_delivery_charge': 0, 'overall_delivery_charge_type': 'fixed', 'vat': 0, 'vat_type': 'fixed'}
    r = client(owner, utt.id).post('/api/purchases/', body, format='json')
    pr = Purchase.objects.filter(company=co).order_by('-id').first()
    prod.refresh_from_db()
    ok('6. Owner (Uttara picked) buys 4 → Uttara 7', r.status_code < 300 and in_branch(utt) == 7, (r.status_code, in_branch(utt), str(r.json())[:120]))
    ok('   branches add up to total', not invariant(), invariant()[:3])
    # ── ৭. "সব শাখা" দেখার সময় সেই ক্রয় বাতিল → উত্তরা থেকেই কমে
    r = o.delete(f'/api/purchases/{pr.id}/')
    prod.refresh_from_db()
    ok('7. Cancelling that purchase (viewing all) takes it back from Uttara', in_branch(utt) == 3 and in_branch(main) == total0 - 5,
       (r.status_code, in_branch(utt), in_branch(main)))
    ok('   branches add up to total', not invariant(), invariant()[:3])

# ── ৮. API
d = o.get(f'/api/branches/stock/?product={prod.id}').json()['data']
ok('8. Branch stock API shows both branches', d['enabled'] and d['stock'][str(prod.id)][str(utt.id)] == in_branch(utt))
ok('   transfer list has the transfer', any(t['to_name'] == 'Uttara' for t in o.get('/api/branches/transfers/').json()['data']))

# পরিষ্কার — শাখা মুছে দোকানকে আগের অবস্থায় (স্টকের মোট আগের মতোই থাকে)
staff.branch = None; staff.is_active = False; staff.save()
for m in (Sale, MoneyReceipt, Expense, Purchase):
    m.objects.filter(company=co).update(branch=None)
StockTransfer.objects.filter(company=co).delete()
BranchStock.objects.filter(branch__company=co).delete()
Branch.objects.filter(company=co).delete()
print(f"\n{sum(res)}/{len(res)} passed")
