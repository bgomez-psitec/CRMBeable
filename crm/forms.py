from django import forms

from accounts.models import User
from crm.models import Company, Round


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'int_code', 'fund', 'country', 'provincia', 'sectors', 'stage',
                  'trl', 'mrl', 'ttm', 'revenue', 'valuation', 'valuation_date']
        widgets = {
            'valuation_date': forms.DateInput(attrs={'type': 'date'}),
        }


class RoundForm(forms.ModelForm):
    class Meta:
        model = Round
        fields = ['type', 'target', 'status', 'rstage', 'start', 'close']
        widgets = {
            'start': forms.DateInput(attrs={'type': 'date'}),
            'close': forms.DateInput(attrs={'type': 'date'}),
        }


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'mfa_enabled',
                  'assigned_companies', 'company', 'is_active']
