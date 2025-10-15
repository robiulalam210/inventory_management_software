from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Company

class CompanyAdminSignupForm(UserCreationForm):
    company_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    is_staff = forms.BooleanField(
        label='Staff status (Can log into admin)',
        required=False,
        help_text='Designates whether the user can log into this admin site.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'is_staff')


class UserForm(UserCreationForm):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=User.Role.choices)
    is_staff = forms.BooleanField(
        label='Staff status (Can log into admin)',
        required=False,
        help_text='Designates whether the user can log into this admin site.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2', 'is_staff')
