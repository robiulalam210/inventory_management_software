# management/commands/complete_sku_reset.py
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from products.models import CompanyProductSequence, Product, Company

class Command(BaseCommand):
    help = 'Completely reset SKU sequences and clear all cached data'

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. DELETE all sequences completely
            CompanyProductSequence.objects.all().delete()
            
            # 2. Reset SQLite sequence table (if using SQLite)
            if 'sqlite' in connection.vendor:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='products_companyproductsequence';")
                print("✓ Reset SQLite sequence table")
            
            # 3. Create FRESH sequences starting from 10000
            companies = Company.objects.all()
            for company in companies:
                CompanyProductSequence.objects.create(
                    company=company,
                    last_number=10000  # This ensures first product gets 10001
                )
                print(f"✓ Created FRESH sequence for {company.name}")
            
            # 4. Optional: Delete all existing product SKUs to force regeneration
            choice = input("Delete all existing product SKUs? (y/n): ")
            if choice.lower() == 'y':
                Product.objects.all().update(sku=None)
                print("✓ Cleared all existing SKUs")
            
            print("🎉 COMPLETE RESET DONE!")
