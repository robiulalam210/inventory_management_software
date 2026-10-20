from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals
        # অ্যাপে Super Admin এর "কোম্পানির ভেতরে দেখা" (X-View-Company header)
        from core.view_as import install
        install()
        # প্যাকেজের পাহারাদার (core/package_gate.py) — settings.py না ছুঁয়েই CompanyMiddleware এর ঠিক পরে বসে।
        # settings.py তে আগেই লেখা থাকলে আবার বসায় না।
        from django.conf import settings
        gate = 'core.package_gate.PackageGateMiddleware'
        mw = list(settings.MIDDLEWARE)
        if gate not in mw:
            anchor = 'core.middleware.CompanyMiddleware'
            mw.insert(mw.index(anchor) + 1 if anchor in mw else len(mw), gate)
            settings.MIDDLEWARE = mw
        # শাখা (core/branches.py) — gate এর পরে বসে; নতুন এন্ট্রিতে শাখা বসানোর signal
        bmw = 'core.branches.BranchMiddleware'
        mw = list(settings.MIDDLEWARE)
        if bmw not in mw:
            mw.insert(mw.index(gate) + 1 if gate in mw else len(mw), bmw)
            settings.MIDDLEWARE = mw
        from core.branches import connect_signals
        connect_signals()
        # শাখা অনুযায়ী স্টক (branch_warehouse/stock.py) — Product এর মোট স্টক বদলালে ঠিক শাখায় বসায়
        from branch_warehouse.stock import connect as connect_branch_stock
        connect_branch_stock()
