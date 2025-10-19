from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Company, StaffRole, Staff

# ==============================
# Company Admin Signup Form
# ==============================
class CompanyAdminSignupForm(UserCreationForm):
    company_name = forms.CharField(
        max_length=150,
        label="Company Name",
        widget=forms.TextInput(attrs={"placeholder": "Company Name"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "Email"})
    )
    is_staff = forms.BooleanField(
        label="Staff status (Can log into admin)",
        required=False,
        initial=True,
        help_text="Designates whether the user can log into this admin site."
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'is_staff')

    def save(self, commit=True, company=None):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_staff = self.cleaned_data.get('is_staff', True)
        if company:
            user.company = company
        user.role = User.Role.ADMIN
        if commit:
            user.save()
        return user


# ==============================
# General User Creation Form
# ==============================
class UserForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "Email"})
    )
    role = forms.ChoiceField(
        choices=User.Role.choices,
        label="Role",
    )
    is_staff = forms.BooleanField(
        label="Staff status (Can log into admin)",
        required=False,
        initial=True,
        help_text="Designates whether the user can log into this admin site."
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2', 'is_staff')

    def save(self, commit=True, company=None):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        user.is_staff = self.cleaned_data.get('is_staff', True)
        if company:
            user.company = company
        if commit:
            user.save()
        return user
