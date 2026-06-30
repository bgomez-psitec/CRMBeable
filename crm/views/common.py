"""Shared imports, constants, and helper functions used across all view modules."""
import pathlib
import re as _re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User

from crm.forms import ColaboracionForm, CompanyForm, ContactoMAForm, IntroductionForm, ProcesoMAForm, RoundForm, UserForm
from crm.models import (
    Colaboracion, ColaboradorContacto, Colaborador, ColaboradorLog, Company,
    ContactoMA, Documento, EstadoColaboracion, EstadoMA, EstadoPresentacion, EtapaRelacion, EtapaRelacionColaborador,
    EtapaInversion, FaseMA, FaseRonda, InboxMessage, Interaction, InteraccionColaboracion, InteraccionMA,
    Introduction, Investor, InvestorContact, InvestorLog, ProcesoMA, ProcesoMAFaseLog,
    RangoAUM, RangoTicket, Round, RoundFaseLog, TipoInversor,
)
from crm.permissions import (
    allowed_company_ids, can_edit, can_see_company, visible_companies, visible_introductions, visible_investors,
)
from crm.utils import (
    MA_ESTADO_W, MA_TERMINAL, COLLAB_TERMINAL, COLLAB_ESTADO_W, ESTADO_W,
    active_rounds, company_invertido, proceso_ma_vendido, proceso_ma_weighted,
    round_invertido, round_weighted,
)

AREA_OPTS = [
    'Unknown', 'Worldwide', 'Southern Europe', 'Northern Europe',
    'Western Europe', 'Central & Eastern Europe', 'North America',
    'South & Central America', 'Northeast Asia', 'Southeast Asia',
    'Australia and Oceania', 'Middle East', 'Africa', 'Other',
]

SECTOR_OPTS = [
    'Advanced Manufacturing and Processing',
    'Advanced Materials',
    'Artificial Intelligence',
    'Data Mining',
    'Industrial Biotechnology',
    'Microelectronics or Nanoelectronics',
    'Nanotechnology',
    'Other',
    'Other ICT',
    'Pharma',
    'Photonics',
]

# ── Multi-level grouping helpers ────────────────────────────────────────────

def _build_groups(items, keyfns):
    """Recursively group a flat list by successive key functions."""
    if not keyfns:
        return items
    raw = {}
    for item in items:
        raw.setdefault(keyfns[0](item), []).append(item)
    result = dict(sorted(raw.items()))
    if len(keyfns) > 1:
        return {k: _build_groups(v, keyfns[1:]) for k, v in result.items()}
    return result


def _parse_groups(params, allowed_keys):
    """Extract and validate up to 3 group params, preventing duplicates."""
    valid = set(allowed_keys)
    g1 = params.get('group1', '')
    g1 = g1 if g1 in valid else ''
    g2 = params.get('group2', '') if g1 else ''
    g2 = g2 if (g2 in valid and g2 != g1) else ''
    g3 = params.get('group3', '') if (g1 and g2) else ''
    g3 = g3 if (g3 in valid and g3 not in (g1, g2)) else ''
    return g1, g2, g3


# ── Pipeline grouping constants ────────────────────────────────────────────────

PRES_GROUP_KEYS = {
    'estado':     lambda i: i.status.nombre if i.status else '— Sin estado —',
    'company':    lambda i: i.company.name if i.company else '—',
    'round':      lambda i: f"{i.company.name} · {i.round.type}" if i.round else '—',
}
PRES_GROUP_LABELS = [
    ('estado', 'Estado'), ('company', 'Participada'), ('round', 'Ronda'),
]

COLAB_PIPE_GROUP_KEYS = {
    'estado':   lambda c: c.status.nombre if c.status else '— Sin estado —',
    'company':  lambda c: c.company.name if c.company else '—',
    'tipo':     lambda c: c.tipo_relacion or '— Sin tipo —',
}
COLAB_PIPE_GROUP_LABELS = [
    ('estado', 'Estado'), ('company', 'Participada'), ('tipo', 'Tipo de relación'),
]

MA_CONTACTO_GROUP_KEYS = {
    'company':  lambda c: c.proceso.company.name if c.proceso else '—',
    'proceso':  lambda c: c.proceso.nombre if c.proceso else '—',
    'estado':   lambda c: c.status.nombre if c.status else '— Sin estado —',
}
MA_CONTACTO_GROUP_LABELS = [
    ('company', 'Participada'), ('proceso', 'Proceso'), ('estado', 'Estado'),
]

INV_GROUP_KEYS = {
    'type':         lambda c: c['investor'].type or '—',
    'country':      lambda c: c['investor'].country or '—',
    'inv_stage':    lambda c: c['investor'].inv_stage or '—',
    'aum':          lambda c: c['investor'].aum or '—',
    'ticket_range': lambda c: c['investor'].ticket_range or '—',
    'pub_status':   lambda c: c['investor'].pub_status or '—',
    'relation':     lambda c: c['investor'].relation.nombre if c['investor'].relation else '—',
}
INV_GROUP_LABELS = [
    ('type', 'Tipo'), ('country', 'País'), ('inv_stage', 'Etapa'),
    ('relation', 'Relación'), ('aum', 'AUM'),
    ('ticket_range', 'Ticket'), ('pub_status', 'Estado Público'),
]

CON_GROUP_KEYS = {
    'investor': lambda c: c.investor.name,
    'role':     lambda c: c.role or '—',
}
CON_GROUP_LABELS = [('investor', 'Inversor'), ('role', 'Cargo')]

TIPO_CONTACTO_OPTS = [
    ('comprador',           'es_comprador',           'Comprador'),
    ('colaborador',         'es_colaborador',         'Colaborador'),
    ('cliente',             'es_cliente',             'Cliente'),
    ('proveedor',           'es_proveedor',           'Proveedor'),
    ('inversor_esporadico', 'es_inversor_esporadico', 'Inversor esporádico'),
]
