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
    
    can_manage_products = models.BooleanField(default=False)
    can_manage_sales = models.BooleanField(default=False)
    can_manage_purchases = models.BooleanField(default=False)
    can_manage_customers = models.BooleanField(default=False)
    can_manage_suppliers = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    
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
        if self.role == self.Role.SUPER_ADMIN:
            self._set_all_permissions(True)
        elif self.role == self.Role.ADMIN:
            self._set_all_permissions(True)
        elif self.role == self.Role.MANAGER:
            self.can_manage_products = True
            self.can_manage_sales = True
            self.can_manage_purchases = True
            self.can_manage_customers = True
            self.can_manage_suppliers = True
            self.can_view_reports = True
            self.can_manage_users = False
        elif self.role == self.Role.STAFF:
            self.can_manage_products = True
            self.can_manage_sales = True
            self.can_manage_purchases = False
            self.can_manage_customers = True
            self.can_manage_suppliers = False
            self.can_view_reports = True
            self.can_manage_users = False
        elif self.role == self.Role.VIEWER:
            self._set_all_permissions(False)
            self.can_view_reports = True

    def _set_all_permissions(self, value):
        self.can_manage_products = value
        self.can_manage_sales = value
        self.can_manage_purchases = value
        self.can_manage_customers = value
        self.can_manage_suppliers = value
        self.can_view_reports = value
        self.can_manage_users = value

    def get_permissions(self):
        return {
            'products': self.can_manage_products,
            'sales': self.can_manage_sales,
            'purchases': self.can_manage_purchases,
            'customers': self.can_manage_customers,
            'suppliers': self.can_manage_suppliers,
            'reports': self.can_view_reports,
            'users': self.can_manage_users,
        }

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