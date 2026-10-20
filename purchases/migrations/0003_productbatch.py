from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('products', '0003_salemode_show_flags'),
        ('purchases', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_no', models.CharField(blank=True, max_length=50, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('qty_received', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=12)),
                ('qty_remaining', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=12)),
                ('received_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='product_batches', to='core.company')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='products.product')),
                ('purchase_item', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batch', to='purchases.purchaseitem')),
            ],
            options={
                'ordering': ['expiry_date', 'received_at', 'id'],
                'indexes': [
                    models.Index(fields=['product', 'expiry_date'], name='purchases_p_product_1b7e3a_idx'),
                    models.Index(fields=['product', 'qty_remaining'], name='purchases_p_product_6c2f0d_idx'),
                    models.Index(fields=['company', 'expiry_date'], name='purchases_p_company_9d41ac_idx'),
                ],
            },
        ),
    ]
