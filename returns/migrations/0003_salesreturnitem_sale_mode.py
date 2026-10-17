from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('returns', '0002_initial'),
        ('products', '0003_salemode_show_flags'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesreturnitem',
            name='sale_mode',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='products.salemode'),
        ),
        migrations.AddField(
            model_name='salesreturnitem',
            name='mode_name',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='salesreturnitem',
            name='base_multiplier',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
