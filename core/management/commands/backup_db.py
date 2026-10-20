"""
ডাটাবেসের ব্যাকআপ: python manage.py backup_db
  • backups/db-2026-10-20-0300.sqlite3 নামে কপি রাখে
  • সার্ভার চালু থাকলেও নিরাপদ (SQLite এর নিজস্ব backup ব্যবস্থা — আধা-লেখা ফাইল কপি হয় না)
  • ১৪টার বেশি পুরনো ব্যাকআপ নিজে মুছে দেয় (--keep দিয়ে বদলানো যায়)
cPanel → Cron Jobs এ প্রতিদিন রাত ৩টায় (Setup Python App পাতার python এর পথ দিন):
  cd /home/meherinm/dokankhata && /home/meherinm/virtualenv/dokankhata/3.11/bin/python manage.py backup_db
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'SQLite ডাটাবেসের তারিখসহ ব্যাকআপ (backups/ ফোল্ডারে)'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=14, help='কয়টা ব্যাকআপ রাখবে (ডিফল্ট ১৪)')

    def handle(self, *args, **opts):
        db = settings.DATABASES['default']
        if 'sqlite3' not in db['ENGINE']:
            raise CommandError('শুধু SQLite এর জন্য। MySQL হলে cPanel এর Backup ব্যবহার করুন।')
        src = Path(db['NAME'])
        out_dir = Path(settings.BASE_DIR) / 'backups'
        out_dir.mkdir(exist_ok=True)
        dst = out_dir / f"db-{datetime.now():%Y-%m-%d-%H%M}.sqlite3"
        with sqlite3.connect(str(src)) as a, sqlite3.connect(str(dst)) as b:
            a.backup(b)
        old = sorted(out_dir.glob('db-*.sqlite3'))[:-max(1, opts['keep'])]
        for f in old:
            f.unlink()
        self.stdout.write(self.style.SUCCESS(
            f'ব্যাকআপ হয়েছে: {dst.name} ({dst.stat().st_size // 1024} KB), পুরনো মোছা: {len(old)}'))
