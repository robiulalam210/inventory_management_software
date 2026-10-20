"""
বাকি খাতা (বিক্রি ছাড়া বাকি) + ওয়ারেন্টির পরীক্ষা — শুধু test/copy database এ চালাবেন (data যোগ করে)।
    python tools/tests/test_khata.py <username>
"""
import os, sys, uuid, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'inventory_api.settings'
import django
django.setup()
import logging; logging.disable(logging.CRITICAL)
from decimal import Decimal as D
from rest_framework.test import APIClient
from core.models import User
from accounts.models import Account
from customers.models import Customer, CustomerDue
from sales.models import Sale, SaleItem
from products.models import Product
from money_receipts.models import MoneyReceipt

u = User.objects.get(username=sys.argv[1] if len(sys.argv) > 1 else 'rahim')
c = APIClient(SERVER_NAME='localhost'); c.force_authenticate(u)
acc = Account.objects.filter(company=u.company, ac_type='Cash').first()
cust = Customer.objects.create(company=u.company, name='Khata Test', phone='019' + str(uuid.uuid4().int)[:8])
prod = Product.objects.filter(company=u.company).first()
today = datetime.date.today().isoformat()
res = []

def ok(name, cond, extra=''):
    res.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name, extra)

def total_due():
    rows = c.get('/api/customers-active/').json()['data']
    return D(str(next(r for r in rows if r['id'] == cust.id)['total_due']))

def bal():
    acc.refresh_from_db(); return acc.balance

def receipt(amount):
    r = c.post('/api/money-receipts/', {'customer_id': cust.id, 'amount': f'{amount:.2f}', 'payment_date': today,
                                        'payment_method': 'Cash', 'account_id': acc.id, 'seller_id': u.id}, format='json')
    assert r.status_code < 300, r.json()
    return r.json()['data']['id']

# 1. পুরনো বাকি ১০০০
r = c.post('/api/customer-dues/', {'customer_id': cust.id, 'amount': '1000', 'kind': 'opening', 'note': 'old khata'}, format='json')
ok('1. Opening due saved', r.status_code == 201, r.json().get('message'))
due1 = CustomerDue.objects.get(customer=cust)
ok('   total_due = 1000', total_due() == D('1000'), total_due())
rem = c.get('/api/reports/customer-due-reminders/').json()['data']['customers']
ok('   in due reminders with 1000', any(x['customer_id'] == cust.id and x['net_due'] == 1000 for x in rem))
led = c.get('/api/reports/customer-ledger/', {'customer': cust.id, 'start': '2000-01-01', 'end': today}).json()['data']['report']
led = led['results'] if isinstance(led, dict) else led
ok('   ledger has the due line', any(e['voucher_no'] == due1.entry_no and e['debit'] == 1000 for e in led))
lst = c.get('/api/customers/', {'amount_type': 'due', 'page_size': 500}).json()['data']
lst = lst['results'] if isinstance(lst, dict) else lst
ok('   customer list "due" filter includes them', any(x['id'] == cust.id for x in lst))

# 2. টাকা পেলাম ৬০০ → বাকি খাতার এন্ট্রিতে বসে, advance নয়
b0 = bal(); m1 = receipt(600)
due1.refresh_from_db(); cust.refresh_from_db()
ok('2. Receipt 600 → due paid 600, no advance', due1.paid_amount == D('600') and cust.advance_balance == 0, f'paid={due1.paid_amount} adv={cust.advance_balance}')
ok('   account +600', bal() - b0 == D('600'), bal() - b0)
ok('   total_due = 400', total_due() == D('400'), total_due())

# 3. বাকিতে বিক্রি
body = {'type': 'normal_sale', 'sale_date': today, 'sale_by': str(u.id), 'items': [{'product_id': prod.id, 'quantity': 1, 'unit_price': 300, 'discount': 0, 'discount_type': 'fixed'}],
        'customer_type': 'saved_customer', 'customer_id': str(cust.id), 'with_money_receipt': 'No', 'paid_amount': 0,
        'overall_vat_type': 'fixed', 'vat': 0, 'overall_service_type': 'fixed', 'service_charge': 0, 'overall_delivery_type': 'fixed',
        'delivery_charge': 0, 'overall_discount_type': 'fixed', 'overall_discount': 0}
r = c.post('/api/sales/', body, format='json'); sale = Sale.objects.get(id=r.json()['data']['id'])
ok('3. Credit sale 300 → total_due = 700', total_due() == D('700'), total_due())

# 4. ৫০০ পেলাম → আগে invoice (৩০০), তারপর বাকি খাতা (২০০)
m2 = receipt(500); sale.refresh_from_db(); due1.refresh_from_db()
ok('4. Receipt 500 → invoice cleared, due +200', sale.due_amount == 0 and due1.paid_amount == D('800'), f'sale_due={sale.due_amount} due_paid={due1.paid_amount}')
ok('   allocation recorded', MoneyReceipt.objects.get(id=m2).allocation.get('dues') == {str(due1.id): '200.00'}, MoneyReceipt.objects.get(id=m2).allocation)
ok('   total_due = 200', total_due() == D('200'), total_due())

# 5. রসিদ বাতিল → সব আগের অবস্থায়
b0 = bal(); r = c.delete(f'/api/money-receipts/{m2}/'); sale.refresh_from_db(); due1.refresh_from_db()
ok('5. Delete receipt → sale due 300, due paid 600', sale.due_amount == D('300') and due1.paid_amount == D('600'), r.status_code)
ok('   account −500', bal() - b0 == D('-500'), bal() - b0)
ok('   total_due = 700', total_due() == D('700'), total_due())

# 6. শোধ শুরু হওয়া এন্ট্রি মোছা যায় না; নতুনটা যায়
r = c.delete(f'/api/customer-dues/{due1.id}/')
ok('6. Partly-paid due cannot be deleted', r.status_code == 400, r.json().get('message'))
r = c.post('/api/customer-dues/', {'customer_id': cust.id, 'amount': '50', 'kind': 'credit'}, format='json')
d2 = r.json()['data']['id']
ok('   new credit 50 → total 750', total_due() == D('750'), total_due())
r = c.delete(f'/api/customer-dues/{d2}/')
ok('   unpaid due can be deleted → 700', r.status_code == 200 and total_due() == D('700'), total_due())

# 7. বেশি দিলে বাকি শোধ, বাড়তি অগ্রিম
m3 = receipt(1000); cust.refresh_from_db(); due1.refresh_from_db()
ok('7. Receipt 1000 on 700 due → 300 advance, due cleared', cust.advance_balance == D('300') and due1.due_amount == 0 and total_due() == 0,
   f'adv={cust.advance_balance} total={total_due()}')

# 8. ভুল ইনপুট
r = c.post('/api/customer-dues/', {'customer_id': cust.id, 'amount': '0'}, format='json')
ok('8. Zero amount rejected', r.status_code == 400)
r = c.post('/api/customer-dues/', {'customer_id': cust.id, 'amount': '10', 'entry_date': '2999-01-01'}, format='json')
ok('   Future date rejected', r.status_code == 400)

# 9. ওয়ারেন্টি
prod.warranty_months = 12; prod.save(update_fields=['warranty_months'])
body['paid_amount'] = 300; body['with_money_receipt'] = 'Yes'; body['payment_method'] = 'Cash'; body['account_id'] = str(acc.id)
r = c.post('/api/sales/', body, format='json'); s2 = Sale.objects.get(id=r.json()['data']['id'])
it = SaleItem.objects.filter(sale=s2).first()
ok('9. Sale item copies 12-month warranty', it.warranty_months == 12, it.warranty_months)
w = c.get('/api/reports/warranty/', {'q': s2.invoice_no}).json()['data']['rows']
ok('   warranty check finds it, active, until +1 year', len(w) == 1 and w[0]['status'] == 'active' and w[0]['warranty_until'][:4] == str(datetime.date.today().year + 1), w[:1])
prod.warranty_months = 0; prod.save(update_fields=['warranty_months'])
it.refresh_from_db()
ok('   later product change does not alter past sale', it.warranty_months == 12)

print(f"\n{sum(res)}/{len(res)} passed")
