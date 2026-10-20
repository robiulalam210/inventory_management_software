"""
আগে থেকেই যেসব দোকানে শাখা আছে (শাখা ধাপ ১): তাদের এখনকার সব স্টক প্রধান শাখায় বসাও।
এরপর অন্য শাখায় বিক্রির আগে "মাল পাঠান" দিয়ে সেই শাখায় মাল পাঠাতে হবে।
শাখা নেই এমন দোকানে কিছুই হয় না। আবার চালালেও ক্ষতি নেই (যেখানে আগে থেকে আছে, বাদ)।
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Branch = apps.get_model('branch_warehouse', 'Branch')
    BranchStock = apps.get_model('branch_warehouse', 'BranchStock')
    Product = apps.get_model('products', 'Product')
    for main in Branch.objects.filter(is_main=True):
        if BranchStock.objects.filter(branch__company_id=main.company_id).exists():
            continue
        rows = [BranchStock(branch_id=main.id, product_id=pid, qty=int(q or 0))
                for pid, q in Product.objects.filter(company_id=main.company_id).values_list('id', 'stock_qty')]
        BranchStock.objects.bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('branch_warehouse', '0002_stocktransfer_stocktransferitem_branchstock'),
        ('products', '__latest__'),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
