from django.db import migrations, models


class Migration(migrations.Migration):
    """
    SupplierPayment.allocation — payment এর টাকা কোন purchase এ কত বসেছিল আর কত advance হয়েছিল তার রেকর্ড।
    বাতিল (cancel) করলে ঠিক এই হিসাব উল্টে দেওয়া হয়।
    """

    dependencies = [
        ('supplier_payment', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierpayment',
            name='allocation',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
