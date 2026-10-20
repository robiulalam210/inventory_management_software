from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0001_initial'),
        ('core', '0001_initial'),
        ('products', '0003_salemode_show_flags'),
    ]

    operations = [
        migrations.CreateModel(
            name='Stocktake',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=30)),
                ('title', models.CharField(blank=True, default='', max_length=150)),
                ('note', models.CharField(blank=True, default='', max_length=300)),
                ('status', models.CharField(choices=[('draft', 'In progress'), ('applied', 'Applied'), ('cancelled', 'Cancelled')], default='draft', max_length=12)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='products.category')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stocktakes', to='core.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.CreateModel(
            name='StockAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=30)),
                ('qty_before', models.IntegerField(default=0)),
                ('qty_after', models.IntegerField(default=0)),
                ('change', models.IntegerField(default=0)),
                ('value_change', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('reason', models.CharField(choices=[('damaged', 'Damaged'), ('expired', 'Expired'), ('lost', 'Lost / stolen'), ('found', 'Found / extra'), ('correction', 'Entry mistake'), ('opening', 'Opening stock'), ('count', 'Stock count'), ('other', 'Other')], default='other', max_length=20)),
                ('note', models.CharField(blank=True, default='', max_length=300)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_adjustments', to='core.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_adjustments', to='products.product')),
                ('stocktake', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='adjustments', to='stockops.stocktake')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', '-created_at'], name='stockops_ad_company_c1f0a1_idx')],
            },
        ),
        migrations.CreateModel(
            name='StocktakeLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_qty', models.IntegerField(default=0)),
                ('counted_qty', models.IntegerField(blank=True, null=True)),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('applied_change', models.IntegerField(blank=True, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='products.product')),
                ('stocktake', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='stockops.stocktake')),
            ],
            options={'ordering': ['product__name', 'id'], 'unique_together': {('stocktake', 'product')}},
        ),
        migrations.CreateModel(
            name='DayClose',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('note', models.CharField(blank=True, default='', max_length=300)),
                ('total_expected', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('total_counted', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('difference', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('closed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('closed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='day_closes', to='core.company')),
            ],
            options={'ordering': ['-date'], 'unique_together': {('company', 'date')}},
        ),
        migrations.CreateModel(
            name='DayCloseLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('type', models.CharField(blank=True, default='', max_length=30)),
                ('money_in', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('money_out', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('expected', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('counted', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('difference', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.account')),
                ('day_close', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='stockops.dayclose')),
            ],
        ),
    ]
