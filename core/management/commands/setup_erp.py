# core/management/commands/setup_erp_fixed.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Company, StaffRole, Staff

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup initial ERP data with proper user-company association'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Superuser username',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@erp.com',
            help='Superuser email',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='12345678',
            help='Superuser password',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting ERP setup...')
        
        # Create super admin company
        company, created = Company.objects.get_or_create(
            name="Super Admin Company",
            defaults={
                'company_code': 'SUPER001',
                'is_active': True,
                'address': 'Main Office',
                'phone': '+1234567890',
                'email': 'admin@supercompany.com',
                'plan_type': Company.PlanType.PREMIUM,
                'max_users': 50,
                'max_products': 10000,
                'max_branches': 10
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created company: {company.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Company already exists: {company.name}')
            )

        # Create default staff roles
        roles_data = [
            {
                'name': 'System Administrator', 
                'role_type': 'management',
                'default_permissions': {
                    'products': True,
                    'sales': True,
                    'purchases': True,
                    'customers': True,
                    'suppliers': True,
                    'reports': True,
                    'users': True,
                }
            },
            {
                'name': 'Sales Manager', 
                'role_type': 'sales',
                'default_permissions': {
                    'products': True,
                    'sales': True,
                    'purchases': False,
                    'customers': True,
                    'suppliers': False,
                    'reports': True,
                    'users': False,
                }
            },
            {
                'name': 'Warehouse Manager', 
                'role_type': 'warehouse',
                'default_permissions': {
                    'products': True,
                    'sales': False,
                    'purchases': True,
                    'customers': False,
                    'suppliers': True,
                    'reports': True,
                    'users': False,
                }
            },
            {
                'name': 'Accountant', 
                'role_type': 'accounts',
                'default_permissions': {
                    'products': False,
                    'sales': True,
                    'purchases': True,
                    'customers': True,
                    'suppliers': True,
                    'reports': True,
                    'users': False,
                }
            },
            {
                'name': 'Support Staff', 
                'role_type': 'support',
                'default_permissions': {
                    'products': True,
                    'sales': True,
                    'purchases': False,
                    'customers': True,
                    'suppliers': False,
                    'reports': False,
                    'users': False,
                }
            },
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
            else:
                # Update existing role with new permissions if needed
                role.default_permissions = role_data['default_permissions']
                role.save()
                self.stdout.write(
                    self.style.WARNING(f'Updated role: {role.name}')
                )

        # Create superuser if requested
        if options['create_superuser']:
            self.create_superuser(
                options['username'],
                options['email'],
                options['password'],
                company
            )

        self.stdout.write(
            self.style.SUCCESS('ERP setup completed successfully!')
        )

    def create_superuser(self, username, email, password, company):
        """Create a superuser with proper company association"""
        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'company': company,
                    'role': User.Role.SUPER_ADMIN,
                    'is_staff': True,
                    'is_superuser': True
                }
            )
            
            if created:
                user.set_password(password)
                user.save()
                
                # Create staff profile
                admin_role = StaffRole.objects.get(name='System Administrator')
                Staff.objects.create(
                    user=user,
                    company=company,
                    role=admin_role,
                    designation='System Administrator',
                    is_main_user=True,
                    employment_type=Staff.EmploymentType.FULL_TIME
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created superuser: {username}')
                )
            else:
                # Update existing user
                user.email = email
                user.company = company
                user.role = User.Role.SUPER_ADMIN
                user.is_staff = True
                user.is_superuser = True
                user.set_password(password)
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Updated existing user: {username} to SUPER_ADMIN')
                )
                
            return user
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )
            return None