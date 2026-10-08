"""
Sidebar menu — desktop app এর sidebar এর হুবহু একই গঠন ও একই permission নিয়ম।

প্রতিটা item:
  title  — দেখানো নাম
  url    — Django url name; None হলে module এখনো তৈরি হয়নি ("Soon")
  perm   — (module, action) — user.get_permissions() এ এটা True হলে দেখায়
  roles  — দিলে শুধু এই role গুলো দেখে (যেমন Audit Log)

একটা একটা module তৈরি হলে শুধু এখানে url বসালেই menu তে চালু হয়ে যায়।
"""

SALES_VIEW = ('sales', 'view')

MENU = [
    {'title': 'Dashboard', 'icon': 'dashboard', 'items': [
        {'title': 'My Dashboard', 'url': 'web:home', 'perm': ('dashboard', 'view'), 'slug': 'dashboard'},
    ]},
    {'title': 'Sales', 'icon': 'cart', 'items': [
        {'title': 'Sale', 'url': 'web:sale_new', 'perm': ('sales', 'create'), 'slug': 'sale'},
        {'title': 'POS Sale', 'url': 'web:pos', 'perm': ('sales', 'create'), 'slug': 'pos-sale'},
        {'title': 'Sale List', 'url': 'web:sales', 'perm': SALES_VIEW, 'slug': 'sale-list'},
    ]},
    {'title': 'Money Receipt', 'icon': 'receipt', 'items': [
        {'title': 'Create Money Receipt', 'url': 'web:receipt_new', 'perm': ('money_receipt', 'create'), 'slug': 'money-receipt-create'},
        {'title': 'Money Receipt List', 'url': 'web:receipts', 'perm': ('money_receipt', 'view'), 'slug': 'money-receipts'},
    ]},
    {'title': 'Purchase', 'icon': 'truck', 'items': [
        {'title': 'Create Purchase', 'url': 'web:purchase_new', 'perm': ('purchases', 'create'), 'slug': 'purchase-create'},
        {'title': 'Purchase List', 'url': 'web:purchases', 'perm': ('purchases', 'view'), 'slug': 'purchases'},
    ]},
    {'title': 'Products', 'icon': 'box', 'items': [
        {'title': 'Products', 'url': None, 'perm': ('products', 'view'), 'slug': 'products'},
    ]},
    {'title': 'Accounts', 'icon': 'wallet', 'items': [
        {'title': 'Accounts', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'accounts'},
    ]},
    {'title': 'Customers', 'icon': 'users', 'items': [
        {'title': 'Customers', 'url': 'web:customers', 'perm': ('customers', 'view'), 'slug': 'customers'},
    ]},
    {'title': 'Supplier', 'icon': 'store', 'items': [
        {'title': 'Supplier List', 'url': 'web:suppliers', 'perm': ('suppliers', 'view'), 'slug': 'suppliers'},
        {'title': 'Supplier Payment', 'url': 'web:supplier_payments', 'perm': ('suppliers', 'view'), 'slug': 'supplier-payments'},
    ]},
    {'title': 'Expense', 'icon': 'expense', 'items': [
        {'title': 'Expense List', 'url': None, 'perm': ('expense', 'view'), 'slug': 'expenses'},
        {'title': 'Expense Head', 'url': None, 'perm': ('expense', 'view'), 'slug': 'expense-heads'},
        {'title': 'Expense Sub Head', 'url': None, 'perm': ('expense', 'view'), 'slug': 'expense-subheads'},
    ]},
    {'title': 'Return', 'icon': 'return', 'items': [
        {'title': 'Sales Return', 'url': None, 'perm': ('return', 'view'), 'slug': 'sales-returns'},
        {'title': 'Bad Stock List', 'url': None, 'perm': ('return', 'view'), 'slug': 'bad-stock'},
        {'title': 'Purchase Return', 'url': None, 'perm': ('return', 'view'), 'slug': 'purchase-returns'},
    ]},
    {'title': 'Reports', 'icon': 'chart', 'items': [
        {'title': 'Sales Report', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-sales'},
        {'title': 'Purchase Report', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-purchases'},
        {'title': 'Profit / Loss', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-profit-loss'},
        {'title': 'Top Selling Products', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-top-products'},
        {'title': 'Low Stock', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-low-stock'},
        {'title': 'Stock Report', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-stock'},
        {'title': 'Customer Ledger', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-customer-ledger'},
        {'title': 'Customer Due / Advance', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-customer-due'},
        {'title': 'Supplier Ledger', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-supplier-ledger'},
        {'title': 'Supplier Due / Advance', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-supplier-due'},
        {'title': 'Expense Report', 'url': None, 'perm': ('reports', 'view'), 'slug': 'report-expenses'},
    ]},
    {'title': 'Administration', 'icon': 'settings', 'items': [
        {'title': 'Staff', 'url': None, 'perm': ('users', 'view'), 'slug': 'staff'},
        {'title': 'Source', 'url': None, 'perm': ('administration', 'view'), 'slug': 'sources'},
        {'title': 'Unit', 'url': None, 'perm': ('administration', 'view'), 'slug': 'units'},
        {'title': 'Brand', 'url': None, 'perm': ('administration', 'view'), 'slug': 'brands'},
        {'title': 'Category', 'url': None, 'perm': ('administration', 'view'), 'slug': 'categories'},
        {'title': 'Group', 'url': None, 'perm': ('administration', 'view'), 'slug': 'groups'},
        {'title': 'Sale Mode', 'url': None, 'perm': ('administration', 'view'), 'slug': 'sale-modes'},
        {'title': 'Company Profile', 'url': None, 'perm': ('administration', 'view'), 'slug': 'profile'},
    ]},
    {'title': 'Income', 'icon': 'income', 'items': [
        {'title': 'Income List', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'incomes'},
        {'title': 'Income Head', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'income-heads'},
    ]},
    {'title': 'Transfer Balance', 'icon': 'transfer', 'items': [
        {'title': 'Account Transfer', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'transfer-create'},
        {'title': 'Transfer List', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'transfers'},
        {'title': 'Transactions', 'url': None, 'perm': ('accounts', 'view'), 'slug': 'transactions'},
    ]},
    {'title': 'Security', 'icon': 'shield', 'items': [
        {'title': 'Audit Log', 'url': None, 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'audit-log'},
        {'title': 'User Permissions', 'url': None, 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'user-permissions'},
    ]},
]


def _allowed(item, perms, role):
    roles = item.get('roles')
    if roles:
        return role in roles
    module, action = item['perm']
    return bool((perms.get(module) or {}).get(action))


def build_menu(user, current_path=''):
    """user এর permission অনুযায়ী ছাঁটা menu — খালি section বাদ"""
    from django.urls import reverse

    perms = user.get_permissions() if hasattr(user, 'get_permissions') else {}
    role = (getattr(user, 'role', '') or '').upper()
    if getattr(user, 'is_superuser', False):
        role = role or 'SUPER_ADMIN'

    sections = []
    for section in MENU:
        items = []
        for item in section['items']:
            if not _allowed(item, perms, role):
                continue
            if item['url']:
                href, ready = reverse(item['url']), True
            else:
                href, ready = reverse('web:soon', args=[item['slug']]), False
            items.append({
                'title': item['title'],
                'href': href,
                'ready': ready,
                'slug': item['slug'],
                'active': current_path.rstrip('/') == href.rstrip('/'),
            })
        if items:
            # কোনো item হুবহু না মিললে, যে item এর ঠিকানা দিয়ে এই page শুরু সেটাই active
            # (যেমন /app/supplier-payments/new/ → "Supplier Payment")
            sections.append({
                'title': section['title'],
                'icon': section['icon'],
                'items': items,
                'open': any(i['active'] for i in items),
            })
    if not any(i['active'] for sec in sections for i in sec['items']):
        cur = current_path.rstrip('/') + '/'
        best = None
        for sec in sections:
            for i in sec['items']:
                h = i['href'].rstrip('/') + '/'
                if i['ready'] and h != '/app/' and cur.startswith(h) and (not best or len(h) > len(best[1]['href'])):
                    best = (sec, i)
        if best:
            best[1]['active'] = True
            best[0]['open'] = True
    return sections


def find_item(slug):
    for section in MENU:
        for item in section['items']:
            if item['slug'] == slug:
                return section, item
    return None, None
