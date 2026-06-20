from django import forms

from accounts.models import User
from crm.models import Colaboracion, Company, ContactoMA, ProcesoMA, Round


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


class ProcesoMAForm(forms.ModelForm):
    class Meta:
        model = ProcesoMA
        fields = ['nombre', 'precio_pedido', 'cerrado', 'start', 'close', 'notes']
        widgets = {
            'start': forms.DateInput(attrs={'type': 'date'}),
            'close': forms.DateInput(attrs={'type': 'date'}),
        }


class ContactoMAForm(forms.ModelForm):
    class Meta:
        model = ContactoMA
        fields = ['comprador', 'status', 'oferta_precio', 'nda_firmado', 'dd_iniciado',
                  'date', 'intro_by', 'next_action', 'next_date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'next_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ColaboracionForm(forms.ModelForm):
    class Meta:
        model = Colaboracion
        fields = ['colaborador', 'tipo_relacion', 'status', 'descripcion',
                  'date', 'intro_by', 'next_action', 'next_date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'next_date': forms.DateInput(attrs={'type': 'date'}),
        }


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'mfa_enabled',
                  'assigned_companies', 'company', 'is_active']
