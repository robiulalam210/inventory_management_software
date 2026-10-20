"""শুরুর ৪টা প্যাকেজ বসানো (ফ্রি ট্রায়াল, স্টার্টার, স্ট্যান্ডার্ড, বিজনেস)। একই code আগে থাকলে বদলায় না।
আগে থেকে চলা কোম্পানির package ফাঁকা থাকে = আগের মতোই সব খোলা।"""
from django.db import migrations


def seed(apps, schema_editor):
    from core.packages import DEFAULT_PACKAGES
    Package = apps.get_model('core', 'Package')
    for p in DEFAULT_PACKAGES:
        Package.objects.get_or_create(code=p['code'], defaults=p)
    PlatformSetting = apps.get_model('core', 'PlatformSetting')
    PlatformSetting.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('core', '0004_packages')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
