from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta
from decimal import Decimal
import uuid


class Company(models.Model):
    class PlanType(models.TextChoices):
        BASIC = 'basic', _('Basic')
        STANDARD = 'standard', _('Standard')
        PREMIUM = 'premium', _('Premium')
    
    name = models.CharField(max_length=150, unique=True)
    trade_license = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='company/logo/', blank=True, null=True)
    
    currency = models.CharField(max_length=10, default='BDT')
    timezone = models.CharField(max_length=50, default='Asia/Dhaka')
    fiscal_year_start = models.DateField(default=date(date.today().year, 7, 1))
    
    plan_type = models.CharField(
        max_length=20, 
        choices=PlanType.choices, 
        default=PlanType.BASIC
    )
    start_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    max_users = models.PositiveIntegerField(default=5)
    max_products = models.PositiveIntegerField(default=1000)
    max_branches = models.PositiveIntegerField(default=3)
    
    company_code = models.CharField(max_length=10, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Company')
        verbose_name_plural = _('Companies')
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['plan_type']),
        ]

    def save(self, *args, **kwargs):
        if not self.company_code:
            self.company_code = self._generate_company_code()
        
        if not self.expiry_date:
            self.expiry_date = date.today() + timedelta(days=365)
        
        if self.expiry_date and self.expiry_date < date.today():
            self.is_active = False
            
        super().save(*args, **kwargs)
    def has_perm(self, perm, obj=None):
            """Does the user have a specific permission?"""
            # Simplest possible answer: Yes, for staff/superusers
            if self.is_active and (self.is_staff or self.is_superuser):
                return True
            return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        # Simplest possible answer: Yes, for staff/superusers
        if self.is_active and (self.is_staff or self.is_superuser):
            return True
        return super().has_module_perms(app_label)
    def _generate_company_code(self):
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase, k=3)) + str(random.randint(100, 999))
        while Company.objects.filter(company_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase, k=3)) + str(random.randint(100, 999))
        return code

    @property
    def is_expired(self):
        return self.expiry_date and self.expiry_date < date.today()

    @property
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def active_user_count(self):
        return self.users.filter(is_active=True).count()

    @property
    def product_count(self):
        return self.products.count()

    def can_add_user(self):
        return self.active_user_count < self.max_users

    def can_add_product(self):
        return self.product_count < self.max_products

    def __str__(self):
        return f"{self.name} ({self.company_code}) - {self.get_plan_type_display()}"


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
        ADMIN = "ADMIN", _("Admin")
        MANAGER = "MANAGER", _("Manager")
        STAFF = "STAFF", _("Staff")
        VIEWER = "VIEWER", _("Viewer")

    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.SUPER_ADMIN
    )
    company = models.ForeignKey(
        'Company', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='users/profile_pictures/', 
        blank=True, 
        null=True
    )
    date_of_birth = models.DateField(blank=True, null=True)
    
    # ===== DASHBOARD PERMISSIONS =====
    can_access_dashboard = models.BooleanField(default=False)
    
    # ===== SALES MODULE PERMISSIONS =====
    sales_view = models.BooleanField(default=False)
    sales_create = models.BooleanField(default=False)
    sales_edit = models.BooleanField(default=False)
    sales_delete = models.BooleanField(default=False)
    
    # ===== MONEY RECEIPT PERMISSIONS =====
    money_receipt_view = models.BooleanField(default=False)
    money_receipt_create = models.BooleanField(default=False)
    money_receipt_edit = models.BooleanField(default=False)
    money_receipt_delete = models.BooleanField(default=False)
    
    # ===== PURCHASES MODULE PERMISSIONS =====
    purchases_view = models.BooleanField(default=False)
    purchases_create = models.BooleanField(default=False)
    purchases_edit = models.BooleanField(default=False)
    purchases_delete = models.BooleanField(default=False)
    
    # ===== PRODUCTS MODULE PERMISSIONS =====
    products_view = models.BooleanField(default=False)
    products_create = models.BooleanField(default=False)
    products_edit = models.BooleanField(default=False)
    products_delete = models.BooleanField(default=False)
    
    # ===== ACCOUNTS MODULE PERMISSIONS =====
    accounts_view = models.BooleanField(default=False)
    accounts_create = models.BooleanField(default=False)
    accounts_edit = models.BooleanField(default=False)
    accounts_delete = models.BooleanField(default=False)
    
    # ===== CUSTOMERS MODULE PERMISSIONS =====
    customers_view = models.BooleanField(default=False)
    customers_create = models.BooleanField(default=False)
    customers_edit = models.BooleanField(default=False)
    customers_delete = models.BooleanField(default=False)
    
    # ===== SUPPLIERS MODULE PERMISSIONS =====
    suppliers_view = models.BooleanField(default=False)
    suppliers_create = models.BooleanField(default=False)
    suppliers_edit = models.BooleanField(default=False)
    suppliers_delete = models.BooleanField(default=False)
    
    # ===== EXPENSE MODULE PERMISSIONS =====
    expense_view = models.BooleanField(default=False)
    expense_create = models.BooleanField(default=False)
    expense_edit = models.BooleanField(default=False)
    expense_delete = models.BooleanField(default=False)
    
    # ===== RETURN MODULE PERMISSIONS =====
    return_view = models.BooleanField(default=False)
    return_create = models.BooleanField(default=False)
    return_edit = models.BooleanField(default=False)
    return_delete = models.BooleanField(default=False)
    
    # ===== REPORTS MODULE PERMISSIONS =====
    reports_view = models.BooleanField(default=False)
    reports_create = models.BooleanField(default=False)  # For generating custom reports
    reports_export = models.BooleanField(default=False)  # For exporting reports
    
    # ===== USERS MODULE PERMISSIONS =====
    users_view = models.BooleanField(default=False)
    users_create = models.BooleanField(default=False)
    users_edit = models.BooleanField(default=False)
    users_delete = models.BooleanField(default=False)
    
    # ===== ADMINISTRATION MODULE PERMISSIONS =====
    administration_view = models.BooleanField(default=False)
    administration_create = models.BooleanField(default=False)
    administration_edit = models.BooleanField(default=False)
    administration_delete = models.BooleanField(default=False)
    
    # ===== SETTINGS PERMISSIONS =====
    settings_view = models.BooleanField(default=False)
    settings_edit = models.BooleanField(default=False)
    
    is_verified = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['is_verified']),
        ]

    def save(self, *args, **kwargs):
        self._set_role_permissions()
        
        if self.role == self.Role.SUPER_ADMIN:
            self.is_staff = True
            self.is_superuser = True
        elif self.role in [self.Role.ADMIN, self.Role.MANAGER]:
            self.is_staff = True
            self.is_superuser = False
        else:
            self.is_staff = False
            self.is_superuser = False
            
        super().save(*args, **kwargs)

    def _set_role_permissions(self):
        """Set permissions based on role"""
        if self.role == self.Role.SUPER_ADMIN:
            self._set_all_permissions(True)
        elif self.role == self.Role.ADMIN:
            self._set_all_permissions(True)
        elif self.role == self.Role.MANAGER:
            self._set_manager_permissions()
        elif self.role == self.Role.STAFF:
            self._set_staff_permissions()
        elif self.role == self.Role.VIEWER:
            self._set_viewer_permissions()

    def _set_all_permissions(self, value):
        """Set all permissions to given value (True for all CRUD)"""
        # Dashboard
        self.can_access_dashboard = value
        
        # Sales - Full CRUD
        self.sales_view = value
        self.sales_create = value
        self.sales_edit = value
        self.sales_delete = value
        
        # Money Receipt - Full CRUD
        self.money_receipt_view = value
        self.money_receipt_create = value
        self.money_receipt_edit = value
        self.money_receipt_delete = value
        
        # Purchases - Full CRUD
        self.purchases_view = value
        self.purchases_create = value
        self.purchases_edit = value
        self.purchases_delete = value
        
        # Products - Full CRUD
        self.products_view = value
        self.products_create = value
        self.products_edit = value
        self.products_delete = value
        
        # Accounts - Full CRUD
        self.accounts_view = value
        self.accounts_create = value
        self.accounts_edit = value
        self.accounts_delete = value
        
        # Customers - Full CRUD
        self.customers_view = value
        self.customers_create = value
        self.customers_edit = value
        self.customers_delete = value
        
        # Suppliers - Full CRUD
        self.suppliers_view = value
        self.suppliers_create = value
        self.suppliers_edit = value
        self.suppliers_delete = value
        
        # Expense - Full CRUD
        self.expense_view = value
        self.expense_create = value
        self.expense_edit = value
        self.expense_delete = value
        
        # Return - Full CRUD
        self.return_view = value
        self.return_create = value
        self.return_edit = value
        self.return_delete = value
        
        # Reports - View and Export only
        self.reports_view = value
        self.reports_create = value
        self.reports_export = value
        
        # Users - Full CRUD
        self.users_view = value
        self.users_create = value
        self.users_edit = value
        self.users_delete = value
        
        # Administration - Full CRUD
        self.administration_view = value
        self.administration_create = value
        self.administration_edit = value
        self.administration_delete = value
        
        # Settings - View and Edit
        self.settings_view = value
        self.settings_edit = value

    def _set_manager_permissions(self):
        """Set permissions for Manager role"""
        # Dashboard
        self.can_access_dashboard = True
        
        # Sales - Full CRUD
        self.sales_view = True
        self.sales_create = True
        self.sales_edit = True
        self.sales_delete = True
        
        # Money Receipt - Full CRUD
        self.money_receipt_view = True
        self.money_receipt_create = True
        self.money_receipt_edit = True
        self.money_receipt_delete = True
        
        # Purchases - Full CRUD
        self.purchases_view = True
        self.purchases_create = True
        self.purchases_edit = True
        self.purchases_delete = True
        
        # Products - Full CRUD
        self.products_view = True
        self.products_create = True
        self.products_edit = True
        self.products_delete = True
        
        # Accounts - Full CRUD
        self.accounts_view = True
        self.accounts_create = True
        self.accounts_edit = True
        self.accounts_delete = True
        
        # Customers - Full CRUD
        self.customers_view = True
        self.customers_create = True
        self.customers_edit = True
        self.customers_delete = True
        
        # Suppliers - Full CRUD
        self.suppliers_view = True
        self.suppliers_create = True
        self.suppliers_edit = True
        self.suppliers_delete = True
        
        # Expense - Full CRUD
        self.expense_view = True
        self.expense_create = True
        self.expense_edit = True
        self.expense_delete = True
        
        # Return - Full CRUD
        self.return_view = True
        self.return_create = True
        self.return_edit = True
        self.return_delete = True
        
        # Reports - View and Export only
        self.reports_view = True
        self.reports_create = True
        self.reports_export = True
        
        # Users - View only (no create/edit/delete)
        self.users_view = True
        self.users_create = False
        self.users_edit = False
        self.users_delete = False
        
        # Administration - Full CRUD
        self.administration_view = True
        self.administration_create = True
        self.administration_edit = True
        self.administration_delete = True
        
        # Settings - View and Edit
        self.settings_view = True
        self.settings_edit = True

    def _set_staff_permissions(self):
        """Set permissions for Staff role"""
        # Dashboard
        self.can_access_dashboard = True
        
        # Sales - Create and View only (no delete)
        self.sales_view = True
        self.sales_create = True
        self.sales_edit = True
        self.sales_delete = False
        
        # Money Receipt - Create and View only
        self.money_receipt_view = True
        self.money_receipt_create = True
        self.money_receipt_edit = True
        self.money_receipt_delete = False
        
        # Purchases - View only (no create/edit/delete)
        self.purchases_view = True
        self.purchases_create = False
        self.purchases_edit = False
        self.purchases_delete = False
        
        # Products - View and Edit only (no create/delete)
        self.products_view = True
        self.products_create = False
        self.products_edit = True
        self.products_delete = False
        
        # Accounts - View only
        self.accounts_view = True
        self.accounts_create = False
        self.accounts_edit = False
        self.accounts_delete = False
        
        # Customers - Create and View only
        self.customers_view = True
        self.customers_create = True
        self.customers_edit = True
        self.customers_delete = False
        
        # Suppliers - View only
        self.suppliers_view = True
        self.suppliers_create = False
        self.suppliers_edit = False
        self.suppliers_delete = False
        
        # Expense - View only
        self.expense_view = True
        self.expense_create = False
        self.expense_edit = False
        self.expense_delete = False
        
        # Return - Create and View only
        self.return_view = True
        self.return_create = True
        self.return_edit = True
        self.return_delete = False
        
        # Reports - View only
        self.reports_view = True
        self.reports_create = False
        self.reports_export = True
        
        # Users - No access
        self.users_view = False
        self.users_create = False
        self.users_edit = False
        self.users_delete = False
        
        # Administration - No access
        self.administration_view = False
        self.administration_create = False
        self.administration_edit = False
        self.administration_delete = False
        
        # Settings - View only
        self.settings_view = True
        self.settings_edit = False

    def _set_viewer_permissions(self):
        """Set permissions for Viewer role"""
        # Dashboard - View only
        self.can_access_dashboard = True
        
        # All modules - View only (no create/edit/delete)
        self.sales_view = True
        self.sales_create = False
        self.sales_edit = False
        self.sales_delete = False
        
        self.money_receipt_view = True
        self.money_receipt_create = False
        self.money_receipt_edit = False
        self.money_receipt_delete = False
        
        self.purchases_view = True
        self.purchases_create = False
        self.purchases_edit = False
        self.purchases_delete = False
        
        self.products_view = True
        self.products_create = False
        self.products_edit = False
        self.products_delete = False
        
        self.accounts_view = True
        self.accounts_create = False
        self.accounts_edit = False
        self.accounts_delete = False
        
        self.customers_view = True
        self.customers_create = False
        self.customers_edit = False
        self.customers_delete = False
        
        self.suppliers_view = True
        self.suppliers_create = False
        self.suppliers_edit = False
        self.suppliers_delete = False
        
        self.expense_view = True
        self.expense_create = False
        self.expense_edit = False
        self.expense_delete = False
        
        self.return_view = True
        self.return_create = False
        self.return_edit = False
        self.return_delete = False
        
        # Reports - View and Export
        self.reports_view = True
        self.reports_create = False
        self.reports_export = True
        
        # Users - No access
        self.users_view = False
        self.users_create = False
        self.users_edit = False
        self.users_delete = False
        
        # Administration - No access
        self.administration_view = False
        self.administration_create = False
        self.administration_edit = False
        self.administration_delete = False
        
        # Settings - View only
        self.settings_view = True
        self.settings_edit = False

    def get_permissions(self):
        """Return all permissions as a structured dictionary"""
        return {
            'dashboard': {
                'view': self.can_access_dashboard
            },
            'sales': {
                'view': self.sales_view,
                'create': self.sales_create,
                'edit': self.sales_edit,
                'delete': self.sales_delete
            },
            'money_receipt': {
                'view': self.money_receipt_view,
                'create': self.money_receipt_create,
                'edit': self.money_receipt_edit,
                'delete': self.money_receipt_delete
            },
            'purchases': {
                'view': self.purchases_view,
                'create': self.purchases_create,
                'edit': self.purchases_edit,
                'delete': self.purchases_delete
            },
            'products': {
                'view': self.products_view,
                'create': self.products_create,
                'edit': self.products_edit,
                'delete': self.products_delete
            },
            'accounts': {
                'view': self.accounts_view,
                'create': self.accounts_create,
                'edit': self.accounts_edit,
                'delete': self.accounts_delete
            },
            'customers': {
                'view': self.customers_view,
                'create': self.customers_create,
                'edit': self.customers_edit,
                'delete': self.customers_delete
            },
            'suppliers': {
                'view': self.suppliers_view,
                'create': self.suppliers_create,
                'edit': self.suppliers_edit,
                'delete': self.suppliers_delete
            },
            'expense': {
                'view': self.expense_view,
                'create': self.expense_create,
                'edit': self.expense_edit,
                'delete': self.expense_delete
            },
            'return': {
                'view': self.return_view,
                'create': self.return_create,
                'edit': self.return_edit,
                'delete': self.return_delete
            },
            'reports': {
                'view': self.reports_view,
                'create': self.reports_create,
                'export': self.reports_export
            },
            'users': {
                'view': self.users_view,
                'create': self.users_create,
                'edit': self.users_edit,
                'delete': self.users_delete
            },
            'administration': {
                'view': self.administration_view,
                'create': self.administration_create,
                'edit': self.administration_edit,
                'delete': self.administration_delete
            },
            'settings': {
                'view': self.settings_view,
                'edit': self.settings_edit
            }
        }

    def has_permission(self, module, action=None):
        """Check if user has specific permission for module and action"""
        permissions = self.get_permissions()
        
        if module not in permissions:
            return False
            
        if action is None:
            # Check if user has any permission for this module
            return any(permissions[module].values())
        
        if action not in permissions[module]:
            return False
            
        return permissions[module][action]

    def can_create(self, module):
        """Check if user can create in module"""
        return self.has_permission(module, 'create')

    def can_edit(self, module):
        """Check if user can edit in module"""
        return self.has_permission(module, 'edit')

    def can_delete(self, module):
        """Check if user can delete in module"""
        return self.has_permission(module, 'delete')

    def can_view(self, module):
        """Check if user can view module"""
        return self.has_permission(module, 'view')

    def has_company_access(self, company):
        if self.role == self.Role.SUPER_ADMIN:
            return True
        return self.company == company

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.username} - {self.get_role_display()} ({self.company.name if self.company else 'No Company'})"
    
class StaffRole(models.Model):
    class RoleType(models.TextChoices):
        MANAGEMENT = 'management', _('Management')
        SALES = 'sales', _('Sales')
        WAREHOUSE = 'warehouse', _('Warehouse')
        ACCOUNTS = 'accounts', _('Accounts')
        SUPPORT = 'support', _('Support')
    
    name = models.CharField(max_length=100, unique=True)
    role_type = models.CharField(
        max_length=20,
        choices=RoleType.choices,
        default=RoleType.SALES
    )
    description = models.TextField(blank=True, null=True)
    external_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    default_permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Staff Role')
        verbose_name_plural = _('Staff Roles')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_type_display()})"


class Staff(models.Model):
    class Status(models.IntegerChoices):
        INACTIVE = 0, _('Inactive')
        ACTIVE = 1, _('Active')
        SUSPENDED = 2, _('Suspended')
        ON_LEAVE = 3, _('On Leave')
    
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', _('Full Time')
        PART_TIME = 'part_time', _('Part Time')
        CONTRACT = 'contract', _('Contract')
        INTERN = 'intern', _('Intern')

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='staff_profile'
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='staff_members'
    )
    role = models.ForeignKey(
        StaffRole, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='staff_members'
    )

    phone = models.CharField(max_length=20, blank=True, null=True)
    alternate_phone = models.CharField(max_length=20, blank=True, null=True)
    image = models.ImageField(upload_to='staff/images/', blank=True, null=True)
    designation = models.CharField(max_length=120, blank=True, null=True)
    
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME
    )
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    
    salary = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    commission = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    bonus = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    is_main_user = models.BooleanField(default=False)
    status = models.IntegerField(
        choices=Status.choices, 
        default=Status.ACTIVE
    )
    
    joining_date = models.DateField(null=True, blank=True)
    leaving_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    address = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Staff')
        verbose_name_plural = _('Staff')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_main_user']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['employment_type']),
        ]

    def save(self, *args, **kwargs):
        if not self.company and self.user and self.user.company:
            self.company = self.user.company
        
        if not self.employee_id:
            self.employee_id = self._generate_employee_id()
            
        super().save(*args, **kwargs)

    def _generate_employee_id(self):
        if self.company:
            prefix = self.company.company_code
            count = Staff.objects.filter(company=self.company).count() + 1
            return f"{prefix}-EMP-{count:04d}"
        return f"EMP-{uuid.uuid4().hex[:8].upper()}"

    @property
    def is_currently_active(self):
        if self.status == self.Status.INACTIVE:
            return False
        if self.leaving_date and self.leaving_date < date.today():
            return False
        return True

    @property
    def employment_duration(self):
        if self.joining_date:
            end_date = self.leaving_date or date.today()
            return (end_date - self.joining_date).days
        return 0

    @property
    def total_compensation(self):
        return self.salary + self.commission + self.bonus

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.designation or 'Staff'} ({self.company.name})"