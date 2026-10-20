"""সময় হয়ে যাওয়া নির্ধারিত মেসেজ তৈরি করে রাখে — কেউ অ্যাপ/ওয়েব না খুললেও।
cPanel এর Cron Jobs এ প্রতি ১০ মিনিটে চালান:
    */10 * * * *  cd /path/to/project && /path/to/venv/bin/python manage.py generate_messages
(না চালালেও কাজ করে — কেউ Messages পেজ/ড্যাশবোর্ড/অ্যাপ খুললে তখনই তৈরি হয়ে যায়।)
"""
from django.core.management.base import BaseCommand

from core.models import Company
from customers.messaging import generate_for_company


class Command(BaseCommand):
    help = "নির্ধারিত সময় পেরিয়ে যাওয়া মেসেজ schedule গুলো থেকে 'পাঠানোর জন্য প্রস্তুত' মেসেজ তৈরি করে"

    def handle(self, *args, **opts):
        total = 0
        for c in Company.objects.filter(is_active=True):
            total += generate_for_company(c)
        self.stdout.write(self.style.SUCCESS(f'{total} টা মেসেজ তৈরি হলো'))
