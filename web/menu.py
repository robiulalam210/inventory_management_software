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
    {'title': 'Platform', 'icon': 'building', 'items': [
        {'title': 'Companies', 'url': 'web:platform_companies', 'roles': ('SUPER_ADMIN',), 'slug': 'platform-companies'},
    ]},
    {'title': 'Dashboard', 'icon': 'dashboard', 'items': [
        {'title': 'My Dashboard', 'url': 'web:home', 'perm': ('dashboard', 'view'), 'slug': 'dashboard'},
    ]},
    # দোকান খাতা — বাকির খাতা (TallyKhata ধরনের): কার কাছে কত পাবো, টাকা পেলাম, বাকিতে বিক্রি, তাগাদা
    {'title': 'Baki Khata', 'icon': 'book', 'feature': True, 'items': [
        {'title': 'Baki Khata', 'url': 'web:khata', 'perm': ('customers', 'view'), 'slug': 'khata'},
    ]},
    {'title': 'Sales', 'icon': 'cart', 'items': [
        {'title': 'Sale', 'url': 'web:sale_new', 'perm': ('sales', 'create'), 'slug': 'sale'},
        {'title': 'POS Sale', 'url': 'web:pos', 'perm': ('sales', 'create'), 'slug': 'pos-sale'},
        {'title': 'Short Sale', 'url': 'web:short_sale', 'perm': ('sales', 'create'), 'slug': 'short-sale'},
        {'title': 'Sale List', 'url': 'web:sales', 'perm': SALES_VIEW, 'slug': 'sale-list'},
        {'title': 'Warranty Check', 'url': 'web:warranty', 'perm': SALES_VIEW, 'slug': 'warranty'},
    ]},
    {'title': 'Online Shop', 'icon': 'cart', 'items': [
        {'title': 'Online Orders', 'url': 'web:shop_orders', 'perm': ('sales', 'view'), 'slug': 'online-orders'},
        {'title': 'Shop Settings', 'url': 'web:shop_settings', 'perm': ('sales', 'edit'), 'slug': 'shop-settings'},
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
        {'title': 'Products', 'url': 'web:products', 'perm': ('products', 'view'), 'slug': 'products'},
    ]},
    {'title': 'Accounts', 'icon': 'wallet', 'items': [
        {'title': 'Accounts', 'url': 'web:accounts', 'perm': ('accounts', 'view'), 'slug': 'accounts'},
    ]},
    {'title': 'Customers', 'icon': 'users', 'items': [
        {'title': 'Customers', 'url': 'web:customers', 'perm': ('customers', 'view'), 'slug': 'customers'},
        {'title': 'Due Reminders', 'url': 'web:due_reminders', 'perm': ('customers', 'view'), 'slug': 'due-reminders'},
    ]},
    {'title': 'Supplier', 'icon': 'store', 'items': [
        {'title': 'Supplier List', 'url': 'web:suppliers', 'perm': ('suppliers', 'view'), 'slug': 'suppliers'},
        {'title': 'Supplier Payment', 'url': 'web:supplier_payments', 'perm': ('suppliers', 'view'), 'slug': 'supplier-payments'},
    ]},
    {'title': 'Expense', 'icon': 'expense', 'items': [
        {'title': 'Expense List', 'url': 'web:expenses', 'perm': ('expense', 'view'), 'slug': 'expenses'},
        {'title': 'Expense Head', 'url': 'web:expense_heads', 'perm': ('expense', 'view'), 'slug': 'expense-heads'},
        {'title': 'Expense Sub Head', 'url': 'web:expense_subheads', 'perm': ('expense', 'view'), 'slug': 'expense-subheads'},
    ]},
    {'title': 'Return', 'icon': 'return', 'items': [
        {'title': 'Sales Return', 'url': 'web:sales_returns', 'perm': ('return', 'view'), 'slug': 'sales-returns'},
        {'title': 'Bad Stock List', 'url': 'web:bad_stock', 'perm': ('return', 'view'), 'slug': 'bad-stock'},
        {'title': 'Purchase Return', 'url': 'web:purchase_returns', 'perm': ('return', 'view'), 'slug': 'purchase-returns'},
    ]},
    {'title': 'Reports', 'icon': 'chart', 'items': [
        {'title': 'Sales Report', 'url': 'web:report_sales', 'perm': ('reports', 'view'), 'slug': 'report-sales'},
        {'title': 'Purchase Report', 'url': 'web:report_purchases', 'perm': ('reports', 'view'), 'slug': 'report-purchases'},
        {'title': 'Profit / Loss', 'url': 'web:report_profit_loss', 'perm': ('reports', 'view'), 'slug': 'report-profit-loss'},
        {'title': 'Top Selling Products', 'url': 'web:report_top_products', 'perm': ('reports', 'view'), 'slug': 'report-top-products'},
        {'title': 'Low Stock', 'url': 'web:report_low_stock', 'perm': ('reports', 'view'), 'slug': 'report-low-stock'},
        {'title': 'Stock Report', 'url': 'web:report_stock', 'perm': ('reports', 'view'), 'slug': 'report-stock'},
        {'title': 'Customer Ledger', 'url': 'web:report_customer_ledger', 'perm': ('reports', 'view'), 'slug': 'report-customer-ledger'},
        {'title': 'Customer Due / Advance', 'url': 'web:report_customer_due', 'perm': ('reports', 'view'), 'slug': 'report-customer-due'},
        {'title': 'Supplier Ledger', 'url': 'web:report_supplier_ledger', 'perm': ('reports', 'view'), 'slug': 'report-supplier-ledger'},
        {'title': 'Supplier Due / Advance', 'url': 'web:report_supplier_due', 'perm': ('reports', 'view'), 'slug': 'report-supplier-due'},
        {'title': 'Expense Report', 'url': 'web:report_expenses', 'perm': ('reports', 'view'), 'slug': 'report-expenses'},
    ]},
    {'title': 'Administration', 'icon': 'settings', 'items': [
        {'title': 'Staff', 'url': 'web:staff', 'perm': ('users', 'view'), 'slug': 'staff'},
        {'title': 'Branches', 'url': 'web:branches', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'branches'},
        {'title': 'Send stock', 'url': 'web:stock_transfers', 'perm': ('products', 'edit'), 'slug': 'stock-transfers'},
        {'title': 'Source', 'url': 'web:sources', 'perm': ('administration', 'view'), 'slug': 'sources'},
        {'title': 'Unit', 'url': 'web:units', 'perm': ('administration', 'view'), 'slug': 'units'},
        {'title': 'Brand', 'url': 'web:brands', 'perm': ('administration', 'view'), 'slug': 'brands'},
        {'title': 'Category', 'url': 'web:categories', 'perm': ('administration', 'view'), 'slug': 'categories'},
        {'title': 'Group', 'url': 'web:groups', 'perm': ('administration', 'view'), 'slug': 'groups'},
        {'title': 'Sale Mode', 'url': 'web:sale_modes', 'perm': ('administration', 'view'), 'slug': 'sale-modes'},
        {'title': 'Company Profile', 'url': 'web:company_profile', 'perm': ('administration', 'view'), 'slug': 'profile'},
    ]},
    {'title': 'Income', 'icon': 'income', 'items': [
        {'title': 'Income List', 'url': 'web:incomes', 'perm': ('accounts', 'view'), 'slug': 'incomes'},
        {'title': 'Income Head', 'url': 'web:income_heads', 'perm': ('accounts', 'view'), 'slug': 'income-heads'},
    ]},
    {'title': 'Transfer Balance', 'icon': 'transfer', 'items': [
        {'title': 'Account Transfer', 'url': 'web:transfer_new', 'perm': ('accounts', 'view'), 'slug': 'transfer-create'},
        {'title': 'Transfer List', 'url': 'web:transfers', 'perm': ('accounts', 'view'), 'slug': 'transfers'},
        {'title': 'Transactions', 'url': 'web:transactions', 'perm': ('accounts', 'view'), 'slug': 'transactions'},
    ]},
    {'title': 'Payroll', 'icon': 'wallet', 'items': [
        {'title': 'Salary Sheet', 'perm': ('payroll', 'view'), 'url': 'web:payroll', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'payroll'},
        {'title': 'Advances', 'perm': ('payroll', 'view'), 'url': 'web:payroll_advances', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'payroll-advances'},
        {'title': 'Payroll Report', 'perm': ('payroll', 'view'), 'url': 'web:payroll_report', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'payroll-report'},
    ]},
    {'title': 'Security', 'icon': 'shield', 'items': [
        {'title': 'Audit Log', 'url': 'web:audit_log', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'audit-log'},
        {'title': 'User Permissions', 'url': 'web:user_permissions', 'roles': ('SUPER_ADMIN', 'ADMIN'), 'slug': 'user-permissions'},
    ]},
]


def _allowed(item, perms, role):
    roles = item.get('roles')
    if roles and role in roles:
        return True
    if roles and not item.get('perm'):
        return False
    module, action = item['perm']
    return bool((perms.get(module) or {}).get(action))


def build_menu(user, current_path=''):
    """user এর permission অনুযায়ী ছাঁটা menu — খালি section বাদ"""
    from django.urls import reverse

    perms = user.get_permissions() if hasattr(user, 'get_permissions') else {}
    role = (getattr(user, 'role', '') or '').upper()
    if getattr(user, 'is_superuser', False):
        role = 'SUPER_ADMIN'
    # কোনো দোকানের সাথে যুক্ত নয় এমন super admin — তার শুধু Platform দরকার, দোকানের menu খালি data দেখাত
    platform_only = role == 'SUPER_ADMIN' and not getattr(user, 'company_id', None)
    # তার নিজের কোনো দোকান নেই — unit/category/product ইত্যাদি বানানোর জায়গা নেই। শুধু কোম্পানি চালানো ও সব কোম্পানির Audit দেখা।
    platform_slugs = {'platform-companies', 'audit-log'}

    # প্যাকেজে নেই এমন মডিউল menu তে থাকে, কিন্তু 🔒 সহ — ক্লিক করলে "আমার প্যাকেজ" পেজ (কী পাওয়া যায় দেখতে পারে)
    plan = None
    if getattr(user, 'company_id', None):
        try:
            from core.packages import plan_for
            plan = plan_for(user.company)
            if plan.legacy:
                plan = None
        except Exception:  # noqa: BLE001
            plan = None
    from core.package_gate import feature_for_web

    # "শাখা" মেনু শুধু তাদের জন্য যারা শাখা নিয়ে কাজ করবে: প্যাকেজে ২+ শাখার অনুমতি আছে, বা আগে থেকেই শাখা আছে।
    # সাধারণ এক-দোকানের মালিক এটা দেখেনই না।
    show_branches = False
    company = getattr(user, 'company', None)
    if company is not None:
        try:
            from branch_warehouse.models import Branch
            if Branch.objects.filter(company=company).exists():
                show_branches = True
            elif plan is None:     # পুরনো (প্যাকেজ ছাড়া) কোম্পানি — কোম্পানির নিজের শাখা-সীমা
                show_branches = (company.max_branches or 0) > 1
            else:
                lim = plan.limit('max_branches')
                show_branches = lim == 0 or lim > 1
        except Exception:  # noqa: BLE001
            show_branches = False

    # "মাল পাঠানো" শুধু যখন সত্যিই ২+ শাখা চালু (শাখা-স্টক চলছে)
    show_transfers = False
    if company is not None and show_branches:
        try:
            from core.branches import active_count
            show_transfers = active_count(company) >= 2
        except Exception:  # noqa: BLE001
            show_transfers = False

    sections = []
    for section in MENU:
        items = []
        for item in section['items']:
            if platform_only and item.get('slug') not in platform_slugs:
                continue
            if not _allowed(item, perms, role):
                continue
            if item.get('slug') == 'branches' and not show_branches:
                continue
            if item.get('slug') == 'stock-transfers' and not show_transfers:
                continue
            if item['url']:
                href, ready = reverse(item['url']), True
            else:
                href, ready = reverse('web:soon', args=[item['slug']]), False
            locked = False
            if plan is not None and item['url']:
                feat = feature_for_web(item['url'].split(':')[-1])
                if feat and not plan.has(feat):
                    locked, href = True, reverse('web:package') + '?f=' + feat
            items.append({
                'title': item['title'],
                'href': href,
                'ready': ready,
                'locked': locked,
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
                'feature': bool(section.get('feature')),
                'locked': all(i['locked'] for i in items),
                'open': any(i['active'] for i in items),
            })
    if not any(i['active'] for sec in sections for i in sec['items']):
        cur = current_path.rstrip('/') + '/'
        best = None
        for sec in sections:
            for i in sec['items']:
                h = i['href'].rstrip('/') + '/'
                if i['ready'] and not i.get('locked') and h != reverse('web:home') and cur.startswith(h) and (not best or len(h) > len(best[1]['href'])):
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
