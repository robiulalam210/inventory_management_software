# core/management/commands/setup_erp.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Company, StaffRole, Staff

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup initial ERP data'

    def handle(self, *args, **options):
        self.stdout.write("Starting ERP setup...")
        
        # 1. Create super admin company
        company, created = Company.objects.get_or_create(
            name="Super Admin Company",
            defaults={
                'trade_license': 'SUPER-ADMIN-LICENSE',
                'address': 'Super Admin Headquarters',
                'phone': '+880000000000', 
                'email': 'superadmin@company.com',
                'website': 'https://superadmin.company.com',
                'company_code': 'SUPER001',
                'plan_type': Company.PlanType.PREMIUM,
                'max_users': 1000,
                'max_products': 100000,
                'max_branches': 100,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created company: {company.name} ({company.company_code})')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Company already exists: {company.name}')
            )

        # 2. Create or update super admin user
        username = 'admin'
        email = 'admin@gmail.com'
        password = 'admin123'
        
        try:
            # Check if super admin already exists
            super_admin = User.objects.filter(username=username).first()
            
            if super_admin:
                # Update existing super admin
                super_admin.email = email
                super_admin.set_password(password)
                super_admin.company = company
                super_admin.role = User.Role.SUPER_ADMIN
                super_admin.is_staff = True
                super_admin.is_superuser = True
                super_admin.is_active = True
                super_admin.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Updated existing super admin: {username}')
                )
            else:
                # Create new super admin
                super_admin = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    company=company,
                    role=User.Role.SUPER_ADMIN
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created new super admin: {username}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating super admin: {str(e)}')
            )
            return

        # 3. Create staff profile for super admin
        try:
            staff_profile, created = Staff.objects.get_or_create(
                user=super_admin,
                defaults={
                    'company': company,
                    'designation': 'System Administrator',
                    'employment_type': Staff.EmploymentType.FULL_TIME,
                    'salary': 0.00,
                    'is_main_user': True,
                    'status': Staff.Status.ACTIVE,
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created staff profile for super admin')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Staff profile already exists for super admin')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating staff profile: {str(e)}')
            )

        # 4. Create default staff roles
        roles_data = [
            {'name': 'System Administrator', 'role_type': 'management', 'external_id': 1},
            {'name': 'Sales Manager', 'role_type': 'sales', 'external_id': 2},
            {'name': 'Warehouse Manager', 'role_type': 'warehouse', 'external_id': 3},
            {'name': 'Accountant', 'role_type': 'accounts', 'external_id': 4},
            {'name': 'Support Staff', 'role_type': 'support', 'external_id': 5},
            {'name': 'Sales Executive', 'role_type': 'sales', 'external_id': 6},
            {'name': 'Store Keeper', 'role_type': 'warehouse', 'external_id': 7},
        ]
        
        roles_created = 0
        for role_data in roles_data:
            role, created = StaffRole.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                roles_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created role: {role.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Role already exists: {role.name}')
                )

        # 5. Assign System Administrator role to super admin's staff profile
        try:
            admin_role = StaffRole.objects.get(name='System Administrator')
            staff_profile.role = admin_role
            staff_profile.save()
            self.stdout.write(
                self.style.SUCCESS(f'✅ Assigned System Administrator role to super admin')
            )
        except StaffRole.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ System Administrator role not found')
            )

        # 6. Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("🏁 ERP SETUP COMPLETED SUCCESSFULLY!"))
        self.stdout.write("="*50)
        self.stdout.write(f"📊 Summary:")
        self.stdout.write(f"   • Company: {company.name}")
        self.stdout.write(f"   • Super Admin: {super_admin.username}")
        self.stdout.write(f"   • Staff Roles: {roles_created} created")
        self.stdout.write(f"   • Company Code: {company.company_code}")
        self.stdout.write("\n🔑 Login Credentials:")
        self.stdout.write(f"   • Username: {username}")
        self.stdout.write(f"   • Password: {password}")
        self.stdout.write(f"   • Email: {email}")
        self.stdout.write("\n🌐 Access URLs:")
        self.stdout.write(f"   • Admin Panel: /admin/")
        self.stdout.write(f"   • API Login: /api/auth/login/")
        self.stdout.write("="*50)