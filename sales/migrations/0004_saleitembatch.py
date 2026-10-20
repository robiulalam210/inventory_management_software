from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0003_productbatch'),
        ('sales', '0003_sale_tendered_amount'),
    ]

    operations = [
        migrations.CreateModel(
            name='SaleItemBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qty', models.DecimalField(decimal_places=3, max_digits=12)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sale_allocations', to='purchases.productbatch')),
                ('sale_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batch_allocations', to='sales.saleitem')),
            ],
        ),
    ]
