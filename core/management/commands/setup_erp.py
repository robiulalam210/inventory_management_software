# core/management/commands/setup_erp.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Company, StaffRole

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup initial ERP data'

    def handle(self, *args, **options):
        # Create super admin company
        company, created = Company.objects.get_or_create(
            name="Super Admin Company",
            defaults={
                'company_code': 'SUPER001',
                'is_active': True
            }
        )
        
        # Create default staff roles
        roles_data = [
            {'name': 'System Administrator', 'role_type': 'management'},
            {'name': 'Sales Manager', 'role_type': 'sales'},
            {'name': 'Warehouse Manager', 'role_type': 'warehouse'},
            {'name': 'Accountant', 'role_type': 'accounts'},
            {'name': 'Support Staff', 'role_type': 'support'},
        ]
        
        for role_data in roles_data:
            role, created = StaffRole.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created role: {role.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('ERP setup completed successfully!')
        )