from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "একটা user কে Super Admin বানায় (কোম্পানি ছাড়া, সব কোম্পানি চালাতে পারে)। ব্যবহার: python manage.py make_superadmin <username>"

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--keep-company', action='store_true',
                            help='user এর company যেমন আছে তেমনই রাখো (ডিফল্টে company খালি করা হয়)')

    def handle(self, *args, **opts):
        try:
            u = User.objects.get(username=opts['username'])
        except User.DoesNotExist:
            raise CommandError(f"'{opts['username']}' নামে কোনো user নেই")
        before = (u.role, u.is_superuser, u.is_staff, u.company_id)
        u.role = User.Role.SUPER_ADMIN
        u.is_superuser = True
        u.is_staff = True
        u.is_active = True
        if not opts['keep_company']:
            u.company = None
        u.save()
        self.stdout.write(self.style.SUCCESS(
            f"{u.username}: role/superuser/staff/company_id আগে {before} → এখন "
            f"({u.role}, {u.is_superuser}, {u.is_staff}, {u.company_id})"))
