import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial'),
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=100)),
                ('kind', models.CharField(choices=[('due_reminder', 'Customer due reminder'), ('stock_alert', 'Low stock & expiry alert (to owner)'), ('daily_summary', 'Daily summary (to owner)'), ('offer', 'Offer / general message (to customers)')], max_length=20)),
                ('frequency', models.CharField(choices=[('daily', 'Every day'), ('weekly', 'Every week'), ('monthly', 'Every month'), ('once', 'Once')], default='daily', max_length=10)),
                ('send_time', models.TimeField(default='09:00')),
                ('weekday', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('day_of_month', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('run_date', models.DateField(blank=True, null=True)),
                ('enabled', models.BooleanField(default=True)),
                ('template', models.TextField(blank=True, default='')),
                ('min_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('min_days', models.PositiveIntegerField(default=0)),
                ('audience', models.CharField(choices=[('all', 'All customers'), ('with_due', 'Customers with due'), ('recent', 'Recent buyers')], default='all', max_length=10)),
                ('recent_days', models.PositiveIntegerField(default=30)),
                ('notify_phone', models.CharField(blank=True, default='', max_length=20)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_schedules', to='core.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-enabled', 'send_time', 'id']},
        ),
        migrations.CreateModel(
            name='OutboxMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(max_length=20)),
                ('recipient_name', models.CharField(blank=True, default='', max_length=120)),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('text', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Ready to send'), ('sent', 'Sent'), ('skipped', 'Skipped')], db_index=True, default='pending', max_length=10)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbox_messages', to='core.company')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='customers.customer')),
                ('schedule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='messages', to='customers.messageschedule')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', 'status'], name='customers_o_company_5a1c3e_idx')],
            },
        ),
    ]
