# reset_migrations.py
import os
import sys
import django

# ডাটাবেস মুছুন
if os.path.exists('db.sqlite3'):
    os.remove('db.sqlite3')
    print("Database deleted")

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_api.settings')
django.setup()

from django.core.management import execute_from_command_line

print("Creating migrations...")

# প্রথমে built-in apps এর মাইগ্রেশন
execute_from_command_line(['manage.py', 'migrate', 'auth', '--fake'])
execute_from_command_line(['manage.py', 'migrate', 'contenttypes', '--fake'])
execute_from_command_line(['manage.py', 'migrate', 'sessions', '--fake'])

# এখন core অ্যাপের জন্য মাইগ্রেশন তৈরি করুন
print("\nCreating migrations for core app...")
execute_from_command_line(['manage.py', 'makemigrations', 'core'])

# অন্যান্য অ্যাপের মাইগ্রেশন
print("\nCreating migrations for other apps...")
execute_from_command_line(['manage.py', 'makemigrations'])

# সব মাইগ্রেশন এপ্লাই করুন
print("\nApplying all migrations...")
execute_from_command_line(['manage.py', 'migrate'])

print("\nCreating superuser...")
execute_from_command_line(['manage.py', 'createsuperuser'])