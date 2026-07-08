from decimal import Decimal, InvalidOperation

from django import forms

from accounts.models import User
from crm.models import (
    Colaboracion, Company, ContactoMA, EstadoInversion, EtapaInversion,
    Facturacion, Fund, Introduction, Nivel, ProcesoMA, RangoAUM, RangoTicket,
    Round, TiempoMercado, TipoInversor,
)

_date_widget = lambda: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def _fmt_es(value):
    """Formatea un Decimal/float en formato ES: miles con '.' y decimales con ','."""
    if value is None:
        return ''
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ''
    # Sin decimales si son .00
    if f == int(f):
        return f'{int(f):,}'.replace(',', '.')
    return f'{f:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _parse_es(raw):
    """Convierte cadena ES ('1.234,56') a Decimal. Devuelve None si vacía."""
    s = raw.strip()
    if not s:
        return None
    s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        raise forms.ValidationError('Introduce un número válido (p. ej. 1.234,56).')


class EsDecimalField(forms.Field):
    """Campo numérico que muestra y acepta formato español (miles='.', decimal=',')."""

    widget = forms.TextInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)
        self.widget.attrs.setdefault('inputmode', 'decimal')
        self.widget.attrs.setdefault('autocomplete', 'off')

    def prepare_value(self, value):
        if isinstance(value, (int, float, Decimal)):
            return _fmt_es(value)
        return value or ''

    def to_python(self, value):
        if not value:
            return None
        return _parse_es(value)


class CompanyForm(forms.ModelForm):
    valuation = EsDecimalField(label='Valoracion_(€)', required=False)
    provincia = forms.ModelChoiceField(
        queryset=None, required=False, label='Provincia',
        empty_label='— Seleccionar —',
    )
    fund = forms.ModelChoiceField(
        queryset=Fund.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='Fondo',
    )
    stage = forms.ModelChoiceField(
        queryset=EstadoInversion.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='Fase',
    )
    trl = forms.ModelChoiceField(
        queryset=Nivel.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='TRL',
    )
    mrl = forms.ModelChoiceField(
        queryset=Nivel.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='MRL',
    )
    ttm = forms.ModelChoiceField(
        queryset=TiempoMercado.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='Time_to_market',
    )
    revenue = forms.ModelChoiceField(
        queryset=Facturacion.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='Facturacion',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from crm.models import Provincia as ProvinciaModel
        self.fields['provincia'].queryset = ProvinciaModel.objects.filter(habilitada=True)

    class Meta:
        model = Company
        fields = ['name', 'int_code', 'fund', 'country', 'provincia', 'stage',
                  'trl', 'mrl', 'ttm', 'revenue', 'valuation', 'valuation_date',
                  'phone', 'website', 'linkedin', 'logo', 'notes']
        labels = {
            'name': 'Nombre',
            'int_code': 'Codigo_interno',
            'country': 'Pais',
            'valuation_date': 'Fecha_de_Valoracion',
        }
        widgets = {
            'country': forms.TextInput(attrs={'list': 'country-list', 'autocomplete': 'off'}),
            'valuation_date': _date_widget(),
        }


class RoundForm(forms.ModelForm):
    target = EsDecimalField(label='Objetivo_(€)', required=False)
    rstage = forms.ModelChoiceField(
        queryset=EtapaInversion.objects.filter(habilitada=True).order_by('orden', 'nombre'),
        required=False, empty_label='— Seleccionar —', label='Etapa',
    )

    class Meta:
        model = Round
        fields = ['type', 'target', 'status', 'rstage', 'start', 'close']
        labels = {
            'type': 'Tipo',
            'status': 'Estado',
            'start': 'Fecha_inicio',
            'close': 'Fecha_cierre',
        }
        widgets = {
            'start': _date_widget(),
            'close': _date_widget(),
        }


class ProcesoMAForm(forms.ModelForm):
    precio_pedido = EsDecimalField(label='Precio_pedido_(€)', required=False)

    class Meta:
        model = ProcesoMA
        fields = ['nombre', 'fase', 'precio_pedido', 'cerrado', 'start', 'close', 'notes']
        labels = {
            'notes': 'Descripcion',
            'start': 'Fecha_inicio',
            'close': 'Fecha_cierre',
        }
        widgets = {
            'start': _date_widget(),
            'close': _date_widget(),
        }


class ContactoMAForm(forms.ModelForm):
    oferta_precio = EsDecimalField(label='Oferta_(€)', required=False)

    class Meta:
        model = ContactoMA
        fields = ['comprador', 'status', 'oferta_precio',
                  'date', 'intro_by', 'next_action', 'next_date', 'notes']
        labels = {
            'status': 'Estado',
            'date': 'Fecha',
            'intro_by': 'Presentado_por',
            'next_action': 'Proxima_accion',
            'next_date': 'Fecha_proxima_accion',
            'notes': 'Notas',
        }
        widgets = {
            'date': _date_widget(),
            'next_date': _date_widget(),
        }


class ColaboracionForm(forms.ModelForm):
    class Meta:
        model = Colaboracion
        fields = ['colaborador', 'investor', 'tipo_relacion', 'status', 'descripcion',
                  'date', 'intro_by', 'next_action', 'next_date', 'notes']
        labels = {
            'tipo_relacion': 'Tipo_de_relacion',
            'status': 'Estado',
            'date': 'Fecha',
            'intro_by': 'Presentado_por',
            'next_action': 'Proxima_accion',
            'next_date': 'Fecha_proxima_accion',
            'notes': 'Notas',
        }
        widgets = {
            'date': _date_widget(),
            'next_date': _date_widget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from crm.models import TipoRelacionColaboracion
        self.fields['tipo_relacion'].queryset = TipoRelacionColaboracion.objects.filter(habilitada=True)
        self.fields['tipo_relacion'].required = False


class IntroductionForm(forms.ModelForm):
    ticket = EsDecimalField(label='Ticket_(€)', required=False)

    class Meta:
        model = Introduction
        fields = ['round', 'investor', 'status', 'ticket', 'date', 'intro_by', 'next_action', 'next_date', 'notes']
        widgets = {
            'date': _date_widget(),
            'next_date': _date_widget(),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'round': 'Ronda',
            'investor': 'Inversor',
            'status': 'Estado_inicial',
            'date': 'Fecha_Introduccion',
            'intro_by': 'Presentado_por',
            'next_action': 'Proximo_paso',
            'next_date': 'Fecha_proximo_paso',
            'notes': 'Notas',
        }


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'mfa_enabled',
                  'assigned_companies', 'company', 'is_active']
