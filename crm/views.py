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


@login_required
def home(request):
    companies = visible_companies(request.user)

    # Tareas pendientes: próximas acciones con fecha en presentaciones, relaciones inversores y M&A
    from datetime import date as _today
    today = _today.today()
    rounds_qs = Round.objects.filter(company__in=companies).prefetch_related('introductions__status', 'introductions__investor')
    tareas_pendientes = sum(
        1 for r in rounds_qs
        for intro in r.introductions.all()
        if intro.next_action or intro.next_date
    )

    kpis = {
        'participadas':        companies.count(),
        'inversores':          Investor.objects.count(),
        'colaboradores':       Colaborador.objects.count(),
        'rondas_activas':      Round.objects.filter(company__in=companies).exclude(status__nombre='Cerrada').count(),
        'ma_activos':          ProcesoMA.objects.filter(company__in=companies, cerrado=False).count(),
        'colaboraciones_activas': Colaboracion.objects.exclude(status__nombre='Descartado').count(),
        'tareas_pendientes':   tareas_pendientes,
    }
    return render(request, 'crm/home.html', {
        'active_nav': 'home',
        'kpis': kpis,
        'user_name': request.user.get_full_name() or request.user.username,
    })


@login_required
def companies(request):
    if request.user.role == 'ceo':
        return redirect('crm:company_detail', pk=request.user.company_id)

    qs = visible_companies(request.user)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q)
    if request.GET.get('open_only'):
        qs = qs.exclude(rounds__status__nombre='Cerrada').distinct()

    group = request.GET.get('group', '')
    cards = []
    for c in qs:
        ar = active_rounds(c)
        target = sum(r.target or 0 for r in ar)
        inv = sum(round_invertido(r) for r in ar)
        pct = round(inv / target * 100) if target else 0
        n_rondas = c.rounds.count()
        n_inv = sum(r.introductions.count() for r in c.rounds.all())
        n_colab = c.colaboraciones.count()
        n_ma = c.procesos_ma.count()
        cards.append({'company': c, 'target': target, 'invertido': inv, 'pct': min(pct, 100),
                      'n_rondas': n_rondas, 'n_inv': n_inv, 'n_colab': n_colab, 'n_ma': n_ma})

    groups = None
    if group in ('stage', 'country', 'fund'):
        groups = {}
        for card in cards:
            key = getattr(card['company'], group) or '—'
            groups.setdefault(key, []).append(card)

    return render(request, 'crm/companies.html', {
        'active_nav': 'companies',
        'cards': cards,
        'groups': groups,
        'group': group,
        'q': q,
        'open_only': request.GET.get('open_only', ''),
        'can_edit': can_edit(request.user),
    })


@login_required
def company_create(request):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = form.save()
            company.sectors = ', '.join(request.POST.getlist('sectors'))
            company.save(update_fields=['sectors'])
            messages.success(request, 'Participada creada.')
            return redirect('crm:company_detail', pk=company.pk)
    else:
        form = CompanyForm()
    return render(request, 'crm/company_form.html', {
        'active_nav': 'companies', 'form': form, 'title': 'Nueva participada',
        'sector_opts': SECTOR_OPTS,
    })


@login_required
def company_detail(request, pk):
    if not can_see_company(request.user, pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=pk)

    # ── POST: nueva colaboración desde modal ─────────────────────────────────
    if request.method == 'POST' and can_edit(request.user):
        colaborador_id = request.POST.get('colaborador')
        if colaborador_id:
            from crm.models import Colaborador as ColabModel
            col_obj = get_object_or_404(ColabModel, pk=colaborador_id)
            Colaboracion.objects.create(
                company=company, colaborador=col_obj,
                tipo_relacion=request.POST.get('tipo_relacion', ''),
                status_id=request.POST.get('status') or None,
                descripcion=request.POST.get('descripcion', ''),
                date=request.POST.get('date') or None,
                intro_by=request.POST.get('intro_by', ''),
                next_action=request.POST.get('next_action', ''),
                next_date=request.POST.get('next_date') or None,
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, f'Colaboración con {col_obj.name} creada.')
        return redirect('crm:company_detail', pk=pk)

    ar = active_rounds(company)
    target = sum(r.target or 0 for r in ar)
    inv = sum(round_invertido(r) for r in ar)
    weighted = sum(round_weighted(r) for r in ar)
    rounds_data = []
    for r in company.rounds.all():
        ri = round_invertido(r)
        pct = round(ri / r.target * 100) if r.target else 0
        rounds_data.append({'round': r, 'invertido': ri, 'pct': min(pct, 100), 'count': r.introductions.count()})

    procesos_ma = company.procesos_ma.all()
    colaboraciones = list(company.colaboraciones.select_related('colaborador', 'status').all())
    estados_colab = list(EstadoColaboracion.objects.all())

    # Kanban columns: pipeline stages + terminal stages
    pipe_stages_colab = [e for e in estados_colab if e.nombre not in COLLAB_TERMINAL]
    end_stages_colab  = [e for e in estados_colab if e.nombre in COLLAB_TERMINAL]

    def colab_stage(stage):
        items = [c for c in colaboraciones if c.status_id == stage.id]
        return {'estado': stage, 'items': items}

    from crm.models import Colaborador as ColabModel
    all_colaboradores = ColabModel.objects.order_by('name')

    return render(request, 'crm/company_detail.html', {
        'active_nav': 'myco' if request.user.role == 'ceo' else 'companies',
        'company': company,
        'kpis': {
            'target': target, 'invertido': inv, 'weighted': weighted,
            'presentaciones_activas': sum(r['round'].introductions.exclude(status__nombre__in=['Descartado', 'No contactado']).count() for r in rounds_data),
        },
        'rounds_data': rounds_data,
        'procesos_ma': procesos_ma,
        'colaboraciones': colaboraciones,
        'pipe_stages_colab': [colab_stage(s) for s in pipe_stages_colab],
        'end_stages_colab':  [colab_stage(s) for s in end_stages_colab],
        'estados_colab': estados_colab,
        'all_colaboradores': all_colaboradores,
        'can_edit': can_edit(request.user),
    })


@login_required
def company_edit(request, pk):
    if not can_edit(request.user) or not can_see_company(request.user, pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            company.sectors = ', '.join(request.POST.getlist('sectors'))
            company.save(update_fields=['sectors'])
            messages.success(request, 'Participada actualizada.')
            return redirect('crm:company_detail', pk=company.pk)
    else:
        form = CompanyForm(instance=company)
    return render(request, 'crm/company_form.html', {
        'active_nav': 'companies', 'form': form, 'title': f'Editar {company.name}',
        'company': company, 'sector_opts': SECTOR_OPTS,
    })


@login_required
def round_create(request, company_pk):
    from datetime import date as _date
    if not can_edit(request.user) or not can_see_company(request.user, company_pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        form = RoundForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.company = company
            r.save()
            if r.status_id:
                RoundFaseLog.objects.create(
                    round=r, fase_id=r.status_id,
                    date=_date.today(),
                    created_by=request.user.get_full_name() or request.user.username,
                )
            messages.success(request, 'Ronda creada.')
            return redirect('crm:round_detail', pk=r.pk)
    else:
        form = RoundForm()
    return render(request, 'crm/round_form.html', {'active_nav': 'companies', 'form': form, 'title': f'Nueva ronda — {company.name}', 'company': company})


@login_required
def round_edit(request, pk):
    from datetime import date as _date
    r = get_object_or_404(Round.objects.select_related('company'), pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, r.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        fase_anterior_id = r.status_id
        form = RoundForm(request.POST, instance=r)
        if form.is_valid():
            form.save()
            if r.status_id and r.status_id != fase_anterior_id:
                RoundFaseLog.objects.create(
                    round=r, fase_id=r.status_id,
                    date=_date.today(),
                    created_by=request.user.get_full_name() or request.user.username,
                )
            messages.success(request, 'Ronda actualizada.')
            return redirect('crm:round_detail', pk=r.pk)
    else:
        form = RoundForm(instance=r)
    return render(request, 'crm/round_form.html', {
        'active_nav': 'companies', 'form': form,
        'title': f'Editar ronda — {r.company.name}', 'round': r,
        'fase_logs': list(r.fase_logs.select_related('fase').order_by('date', 'pk')),
        'fases_ronda': list(FaseRonda.objects.order_by('pk')),
    })


@login_required
def round_detail(request, pk):
    r = get_object_or_404(Round.objects.select_related('company', 'status'), pk=pk)
    if not can_see_company(request.user, r.company_id):
        return HttpResponseForbidden()

    if request.method == 'POST' and can_edit(request.user):
        contact_type = request.POST.get('contact_type', 'investor')
        investor_id = request.POST.get('investor') if contact_type == 'investor' else None
        colaborador_id = request.POST.get('colaborador') if contact_type == 'colaborador' else None
        status_id = request.POST.get('status') or None
        ticket = request.POST.get('ticket') or None
        date = request.POST.get('date') or None
        intro_by = request.POST.get('intro_by', '')
        next_action = request.POST.get('next_action', '')
        next_date = request.POST.get('next_date') or None
        notes = request.POST.get('notes', '')
        if investor_id:
            investor_obj = get_object_or_404(Investor, pk=investor_id)
            Introduction.objects.create(
                round=r, company=r.company, investor=investor_obj,
                status_id=status_id, ticket=ticket, date=date,
                intro_by=intro_by, next_action=next_action,
                next_date=next_date, notes=notes,
            )
            messages.success(request, f'{investor_obj.name} añadido a la ronda.')
        elif colaborador_id:
            colab_obj = get_object_or_404(Colaborador, pk=colaborador_id)
            Introduction.objects.create(
                round=r, company=r.company, colaborador=colab_obj,
                status_id=status_id, ticket=ticket, date=date,
                intro_by=intro_by, next_action=next_action,
                next_date=next_date, notes=notes,
            )
            messages.success(request, f'{colab_obj.name} añadido a la ronda.')
        return redirect(f"{request.path}?tab={request.POST.get('tab', 'matriz')}")

    intros = r.introductions.select_related('investor', 'colaborador', 'status').all()
    q = request.GET.get('q', '').strip().lower()
    if q:
        intros = [i for i in intros if i.contact and q in str(i.contact).lower()]

    tab = request.GET.get('tab', 'matriz')
    estados = list(EstadoPresentacion.objects.all())

    inv = round_invertido(r)
    pct = round(inv / r.target * 100) if r.target else 0
    pipe_intros = [i for i in r.introductions.all() if not i.status or i.status.nombre not in ('Descartado', 'Invertido')]
    desc_intros = [i for i in r.introductions.all() if i.status and i.status.nombre == 'Descartado']
    inv_intros = [i for i in r.introductions.all() if i.status and i.status.nombre == 'Invertido']

    kpis = {
        'target': r.target or 0, 'total_count': r.introductions.count(),
        'invertido': inv, 'pct': pct, 'inv_count': len(inv_intros),
        'weighted': round_weighted(r), 'other_count': len(pipe_intros),
        'pipe_total': sum(i.ticket or 0 for i in pipe_intros), 'pipe_count': len(pipe_intros),
        'desc_total': sum(i.ticket or 0 for i in desc_intros), 'desc_count': len(desc_intros),
    }

    from crm.utils import ESTADO_W
    pipe_stages = [e for e in estados if e.nombre not in ('Invertido', 'Descartado')]
    end_stages = [e for e in estados if e.nombre in ('Invertido', 'Descartado')]

    def stage_data(stage):
        items = [i for i in intros if i.status_id == stage.id]
        return {'estado': stage, 'items': items, 'total': sum(i.ticket or 0 for i in items),
                'peso': int((ESTADO_W.get(stage.nombre, 0)) * 100)}

    all_investors = visible_investors(request.user).order_by('name')
    all_colaboradores = Colaborador.objects.order_by('name')

    from collections import defaultdict
    _fase_dates_r: dict = defaultdict(list)
    for log in r.fase_logs.order_by('date', 'pk'):
        _fase_dates_r[log.fase_id].append(log.date)

    return render(request, 'crm/round_detail.html', {
        'active_nav': 'companies',
        'round': r, 'company': r.company,
        'kpis': kpis, 'tab': tab, 'q': request.GET.get('q', ''),
        'intros': intros, 'estados': estados,
        'pipe_stages': [stage_data(s) for s in pipe_stages],
        'end_stages': [stage_data(s) for s in end_stages],
        'can_edit': can_edit(request.user),
        'all_investors': all_investors,
        'all_colaboradores': all_colaboradores,
        'fases_ronda': FaseRonda.objects.order_by('pk'),
        'fase_dates': dict(_fase_dates_r),
    })


@login_required
def intro_set_status(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    intro = get_object_or_404(Introduction, pk=pk)
    if not can_see_company(request.user, intro.company_id):
        return HttpResponseForbidden()
    estado_id = request.POST.get('estado_id')
    estado = get_object_or_404(EstadoPresentacion, pk=estado_id)
    estado_anterior = intro.status.nombre if intro.status else '—'
    intro.status = estado
    intro.save(update_fields=['status'])

    # Registrar cambio de estado en la cronología del inversor/colaborador
    from datetime import date as _date
    autor = request.user.get_full_name() or request.user.username
    nota = f'Estado actualizado: {estado_anterior} → {estado.nombre} (Ronda {intro.round.type} · {intro.company.name})'
    if intro.investor_id:
        InvestorLog.objects.create(
            investor_id=intro.investor_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='ronda', round_id=intro.round_id,
        )
    elif intro.colaborador_id:
        from crm.models import ColaboradorLog
        ColaboradorLog.objects.create(
            colaborador_id=intro.colaborador_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='ronda', round_id=intro.round_id,
        )

    next_url = request.POST.get('next', '')
    if next_url == 'pipeline':
        return redirect('crm:presentaciones_pipeline')
    return redirect(reverse('crm:round_detail', kwargs={'pk': intro.round_id}) + '?tab=pipeline')


@login_required
def intro_chrono(request, pk):
    """GET → JSON con logs del inversor para esa ronda. POST → crea log."""
    intro = get_object_or_404(Introduction.objects.select_related('round__company', 'investor'), pk=pk)
    if not can_see_company(request.user, intro.company_id):
        return HttpResponseForbidden()
    if not intro.investor_id:
        return JsonResponse({'logs': []})

    if request.method == 'POST':
        if not can_edit(request.user):
            return JsonResponse({'ok': False}, status=403)
        from datetime import date as _date
        log_type = request.POST.get('type', 'Nota')
        summary  = request.POST.get('summary', '').strip()
        log_date = request.POST.get('date') or None
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f:
            investor = intro.investor
            saved_path = _save_contact_doc(f, 'Inversores', investor.name)
            actual_filename = pathlib.Path(saved_path).name
            slug = _re.sub(r'[^\w\-.]', '_', investor.name.strip())
            attachment_url = reverse('crm:docs_contactos_download',
                                     args=('inversores', slug, actual_filename))
        InvestorLog.objects.create(
            investor_id=intro.investor_id,
            type=log_type,
            date=log_date or _date.today(),
            summary=summary,
            created_by=request.user.get_full_name() or request.user.username,
            context='ronda',
            round_id=intro.round_id,
            attachment_url=attachment_url,
        )
        return JsonResponse({'ok': True})

    from django.db.models import Q
    logs = InvestorLog.objects.filter(
        Q(investor_id=intro.investor_id, round_id=intro.round_id) |
        Q(investor_id=intro.investor_id, type='Estado',
          summary__icontains=intro.round.company.name, round_id__isnull=True)
    ).order_by('-date', '-pk')
    data = [{'date': (l.date.strftime('%d %b %Y') if l.date else '—'),
             'type': l.type, 'summary': l.summary or ''} for l in logs]
    return JsonResponse({'logs': data, 'investor': intro.investor.name,
                         'round': f'{intro.round.type} · {intro.round.company.name}'})


@login_required
def intro_edit(request, pk):
    """Edita los campos de una presentación (ticket, estado, próximo paso, notas…)."""
    intro = get_object_or_404(Introduction, pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, intro.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        tab = request.POST.get('tab', 'matriz')
        intro.status_id  = request.POST.get('status') or intro.status_id
        intro.ticket     = request.POST.get('ticket') or None
        intro.date       = request.POST.get('date') or None
        intro.intro_by   = request.POST.get('intro_by', '')
        intro.next_action = request.POST.get('next_action', '')
        intro.next_date  = request.POST.get('next_date') or None
        intro.notes      = request.POST.get('notes', '')
        intro.save(update_fields=['status', 'ticket', 'date', 'intro_by', 'next_action', 'next_date', 'notes'])
        messages.success(request, 'Presentación actualizada.')
        return redirect(reverse('crm:round_detail', kwargs={'pk': intro.round_id}) + f'?tab={tab}')
    return HttpResponseForbidden()


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


# ── Pipeline grouping helpers ────────────────────────────────────────────────

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


# ── Investors ────────────────────────────────────────────────────────────────

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


@login_required
def investors(request):
    qs = visible_investors(request.user)
    q              = request.GET.get('q', '').strip()
    tipo_filter    = request.GET.get('tipo', '')
    cat_filter     = request.GET.get('categoria', '')
    tipoinv_filter = request.GET.get('tipo_inv', '')
    view = request.GET.get('view', 'list')

    if q:
        qs = qs.filter(
            models.Q(name__icontains=q)
            | models.Q(type__icontains=q)
            | models.Q(country__icontains=q)
            | models.Q(sectors__icontains=q)
        )
    if tipo_filter:
        qs = qs.filter(type=tipo_filter)
    if cat_filter:
        qs = qs.filter(inv_stage__icontains=cat_filter)
    if tipoinv_filter:
        qs = qs.filter(tipo_inversion__icontains=tipoinv_filter)

    g1, g2, g3 = _parse_groups(request.GET, INV_GROUP_KEYS.keys())

    cards = []
    for v in qs.select_related('relation'):
        active = v.introductions.exclude(status__nombre__in=['Descartado', 'No contactado']).count()
        cards.append({'investor': v, 'active': active})

    active_groups = [g for g in (g1, g2, g3) if g]
    groups = _build_groups(cards, [INV_GROUP_KEYS[g] for g in active_groups]) if active_groups else None

    etapas = list(EtapaRelacion.objects.all())
    pipe_stages = []
    for etapa in etapas:
        items = [c for c in cards if c['investor'].relation_id == etapa.pk]
        pipe_stages.append({'etapa': etapa, 'items': items})
    sin_etapa = [c for c in cards if c['investor'].relation_id is None]
    if sin_etapa:
        pipe_stages.insert(0, {'etapa': None, 'items': sin_etapa})

    return render(request, 'crm/investors.html', {
        'active_nav': 'investors', 'cards': cards, 'groups': groups,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': INV_GROUP_LABELS, 'q': q,
        'view': view, 'pipe_stages': pipe_stages,
        'can_edit': can_edit(request.user),
        'etapas_relacion': EtapaRelacion.objects.all(),
        'sector_opts': SECTOR_OPTS,
        'tipo_inversor_choices': TipoInversor.choices,
        'etapa_inversion_choices': EtapaInversion.choices,
        'tipo_filter': tipo_filter,
        'cat_filter': cat_filter,
        'tipoinv_filter': tipoinv_filter,
    })


# ── Investor contacts ────────────────────────────────────────────────────────

CON_GROUP_KEYS = {
    'investor': lambda c: c.investor.name,
    'role':     lambda c: c.role or '—',
}
CON_GROUP_LABELS = [('investor', 'Inversor'), ('role', 'Cargo')]


@login_required
def investor_contacts(request):
    qs = InvestorContact.objects.select_related('investor').all()
    if request.user.role != 'admin':
        visible_ids = visible_investors(request.user).values_list('pk', flat=True)
        qs = qs.filter(investor_id__in=visible_ids)

    q = request.GET.get('q', '').strip()
    investor_id = request.GET.get('investor', '')

    if q:
        qs = qs.filter(
            models.Q(name__icontains=q)
            | models.Q(role__icontains=q)
            | models.Q(email__icontains=q)
            | models.Q(investor__name__icontains=q)
        )
    if investor_id:
        qs = qs.filter(investor_id=investor_id)

    contacts = list(qs.order_by('investor__name', 'name'))

    g1, g2, _ = _parse_groups(request.GET, CON_GROUP_KEYS.keys())
    active_groups = [g for g in (g1, g2) if g]
    groups = _build_groups(contacts, [CON_GROUP_KEYS[g] for g in active_groups]) if active_groups else None

    all_investors = visible_investors(request.user).order_by('name')

    return render(request, 'crm/investor_contacts.html', {
        'active_nav': 'investors', 'contacts': contacts, 'groups': groups,
        'q': q, 'investor_id': investor_id,
        'group1': g1, 'group2': g2,
        'group_labels': CON_GROUP_LABELS,
        'all_investors': all_investors,
    })


@login_required
def colaborador_contacts(request):
    from crm.models import ColaboradorContacto
    qs = ColaboradorContacto.objects.select_related('colaborador').all()
    q = request.GET.get('q', '').strip()
    colaborador_id = request.GET.get('colaborador', '')
    if q:
        qs = qs.filter(
            models.Q(name__icontains=q) | models.Q(role__icontains=q)
            | models.Q(email__icontains=q) | models.Q(colaborador__name__icontains=q)
        )
    if colaborador_id:
        qs = qs.filter(colaborador_id=colaborador_id)
    contacts = list(qs.order_by('colaborador__name', 'name'))
    all_colaboradores = Colaborador.objects.order_by('name')
    return render(request, 'crm/colaborador_contacts.html', {
        'active_nav': 'colaboradores', 'contacts': contacts,
        'q': q, 'colaborador_id': colaborador_id,
        'all_colaboradores': all_colaboradores,
    })


@login_required
def all_contacts(request):
    from crm.models import InvestorContact, ColaboradorContacto
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')  # 'investor' | 'colaborador' | ''

    inv_qs = InvestorContact.objects.select_related('investor').all()
    col_qs = ColaboradorContacto.objects.select_related('colaborador').all()

    if q:
        inv_qs = inv_qs.filter(
            models.Q(name__icontains=q) | models.Q(role__icontains=q)
            | models.Q(email__icontains=q) | models.Q(phone__icontains=q)
            | models.Q(investor__name__icontains=q)
        )
        col_qs = col_qs.filter(
            models.Q(name__icontains=q) | models.Q(role__icontains=q)
            | models.Q(email__icontains=q) | models.Q(phone__icontains=q)
            | models.Q(colaborador__name__icontains=q)
        )

    contacts = []
    if tipo != 'colaborador':
        for c in inv_qs.order_by('name'):
            contacts.append({
                'pk': c.pk, 'tipo': 'investor',
                'name': c.name, 'role': c.role, 'email': c.email, 'phone': c.phone,
                'parent_name': c.investor.name, 'parent_pk': c.investor.pk,
            })
    if tipo != 'investor':
        for c in col_qs.order_by('name'):
            contacts.append({
                'pk': c.pk, 'tipo': 'colaborador',
                'name': c.name, 'role': c.role, 'email': c.email, 'phone': c.phone,
                'parent_name': c.colaborador.name, 'parent_pk': c.colaborador.pk,
            })

    contacts.sort(key=lambda x: x['name'].lower())
    return render(request, 'crm/all_contacts.html', {
        'active_nav': 'contacts', 'contacts': contacts,
        'q': q, 'tipo': tipo, 'can_edit': can_edit(request.user),
        'all_investors': Investor.objects.order_by('name'),
        'all_colaboradores': Colaborador.objects.order_by('name'),
    })


@login_required
def contact_edit(request):
    if not can_edit(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    from crm.models import InvestorContact, ColaboradorContacto
    tipo = request.POST.get('tipo')
    pk = request.POST.get('pk')
    if tipo == 'investor':
        obj = get_object_or_404(InvestorContact, pk=pk)
    elif tipo == 'colaborador':
        obj = get_object_or_404(ColaboradorContacto, pk=pk)
    else:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest()
    obj.name  = request.POST.get('name', '').strip()
    obj.role  = request.POST.get('role', '').strip()
    obj.email = request.POST.get('email', '').strip()
    obj.phone = request.POST.get('phone', '').strip()
    obj.save()

    # Asignar también a otro inversor o colaborador
    assign_tipo = request.POST.get('assign_tipo', '')
    assign_pk   = request.POST.get('assign_pk', '').strip()
    if assign_tipo and assign_pk:
        if assign_tipo == 'investor':
            inv = get_object_or_404(Investor, pk=assign_pk)
            InvestorContact.objects.create(
                investor=inv, name=obj.name, role=obj.role,
                email=obj.email, phone=obj.phone,
            )
        elif assign_tipo == 'colaborador':
            col = get_object_or_404(Colaborador, pk=assign_pk)
            ColaboradorContacto.objects.create(
                colaborador=col, name=obj.name, role=obj.role,
                email=obj.email, phone=obj.phone,
            )

    return redirect(request.POST.get('next', 'crm:all_contacts'))


@login_required
def investor_detail(request, pk):
    investor = get_object_or_404(Investor, pk=pk)
    if request.user.role == 'ceo' and not visible_investors(request.user).filter(pk=pk).exists():
        return HttpResponseForbidden()

    intros = investor.introductions.select_related('company', 'round', 'status').all()
    if request.user.role != 'admin':
        intros = intros.filter(company_id__in=allowed_company_ids(request.user))

    colaboraciones = investor.colaboraciones.select_related('company', 'status').all()
    contactos_ma = investor.contactos_ma.select_related('proceso__company', 'status').all()
    if request.user.role != 'admin':
        allowed = allowed_company_ids(request.user)
        colaboraciones = colaboraciones.filter(company_id__in=allowed)
        contactos_ma = contactos_ma.filter(proceso__company_id__in=allowed)

    # ── KPIs Rondas ────────────────────────────────────────────────────────────
    INTRO_TERMINAL = ('Descartado', 'No contactado')
    intros_activas = [i for i in intros if i.status and i.status.nombre not in INTRO_TERMINAL]
    intros_invertidas = [i for i in intros if i.status and i.status.nombre == 'Invertido']
    intros_descartadas = [i for i in intros if i.status and i.status.nombre == 'Descartado']
    ticket_invertido = sum(i.ticket or 0 for i in intros_invertidas)
    ticket_weighted = sum(
        (i.ticket or 0) * ESTADO_W.get(i.status.nombre if i.status else '', Decimal('0'))
        for i in intros if not i.status or i.status.nombre != 'Invertido'
    )

    # ── KPIs M&A ───────────────────────────────────────────────────────────────
    ma_activos = [c for c in contactos_ma if not c.status or c.status.nombre not in MA_TERMINAL]
    ma_vendidos = [c for c in contactos_ma if c.status and c.status.nombre == 'Vendido']
    ma_descartados = [c for c in contactos_ma if c.status and c.status.nombre == 'Descartado']
    ma_mejor_oferta = max((c.oferta_precio or 0 for c in contactos_ma), default=0)
    ma_weighted = sum(
        (c.oferta_precio or 0) * MA_ESTADO_W.get(c.status.nombre if c.status else '', Decimal('0'))
        for c in contactos_ma if not c.status or c.status.nombre != 'Vendido'
    )

    # ── KPIs Colaboraciones ────────────────────────────────────────────────────
    colab_activas = [c for c in colaboraciones if not c.status or c.status.nombre not in COLLAB_TERMINAL]
    colab_firmadas = [c for c in colaboraciones if c.status and c.status.nombre == 'Activo']
    colab_descartadas = [c for c in colaboraciones if c.status and c.status.nombre == 'Descartado']

    chrono = []
    for log in investor.logs.select_related('round__company', 'proceso_ma__company', 'colaboracion__company').all():
        if request.user.role == 'admin' or not log.round or can_see_company(request.user, log.round.company_id):
            ctx = 'ronda' if log.round else ('ma' if log.proceso_ma else ('colaboracion' if log.colaboracion else (log.context or '')))
            chrono.append({'date': log.date, 'type': log.type, 'summary': log.summary,
                            'company': log.round.company if log.round else None, 'round': log.round,
                            'proceso_ma': log.proceso_ma, 'colaboracion': log.colaboracion,
                            'process_label': log.process_label(),
                            'editable': True, 'id': log.id, 'created_by': log.created_by,
                            'attachment_url': log.attachment_url, 'context': ctx,
                            'delete_url': reverse('crm:investor_log_delete', args=[log.id])})
    for it in intros:
        for interaction in it.interactions.all():
            chrono.append({'date': interaction.date, 'type': interaction.type or 'Nota', 'summary': interaction.note,
                            'company': it.company, 'round': it.round, 'proceso_ma': None, 'colaboracion': None,
                            'process_label': f'{it.company.name} · {it.round.type}',
                            'editable': True, 'id': interaction.id, 'created_by': '', 'context': 'ronda',
                            'delete_url': reverse('crm:interaction_delete', args=[interaction.id])})
    from datetime import date as _date
    chrono.sort(key=lambda x: x['date'] or _date.min, reverse=True)
    last_contact = max((x['date'] for x in chrono if x['date']), default=None)

    # Procesos para el selector del modal de log
    from crm.models import ProcesoMA, Colaboracion as ColaboracionModel
    log_rounds = Round.objects.filter(introductions__investor=investor).select_related('company').distinct()
    log_ma     = ProcesoMA.objects.filter(contactos__investor=investor).select_related('company').distinct()
    log_colabs = ColaboracionModel.objects.filter(investor=investor).select_related('company').distinct()

    investor_companies = Company.objects.filter(
        rounds__introductions__investor=investor
    ).distinct()
    return render(request, 'crm/investor_detail.html', {
        'active_nav': 'investors', 'investor': investor, 'intros': intros, 'chrono': chrono,
        'colaboraciones': colaboraciones, 'contactos_ma': contactos_ma,
        'last_contact': last_contact, 'can_edit': can_edit(request.user),
        'is_admin': request.user.role == 'admin',
        'investor_companies': investor_companies,
        'log_rounds': log_rounds, 'log_ma': log_ma, 'log_colabs': log_colabs,
        'etapas_relacion': EtapaRelacion.objects.all(),
        'tipo_inversor_choices': TipoInversor.choices,
        'etapa_inversion_choices': EtapaInversion.choices,
        'rango_ticket_choices': RangoTicket.choices,
        'rango_aum_choices': RangoAUM.choices,
        'sector_opts': SECTOR_OPTS, 'area_opts': AREA_OPTS,
        # KPIs Rondas
        'intros_activas_count': len(intros_activas),
        'intros_descartadas_count': len(intros_descartadas),
        'ticket_invertido': ticket_invertido,
        'ticket_weighted': ticket_weighted,
        # KPIs M&A
        'ma_activos_count': len(ma_activos),
        'ma_descartados_count': len(ma_descartados),
        'ma_vendidos_count': len(ma_vendidos),
        'ma_mejor_oferta': ma_mejor_oferta,
        'ma_weighted': ma_weighted,
        # KPIs Colaboraciones
        'colab_activas_count': len(colab_activas),
        'colab_firmadas_count': len(colab_firmadas),
        'colab_descartadas_count': len(colab_descartadas),
    })


@login_required
def investor_set_relation(request, pk):
    if request.method == 'POST' and can_edit(request.user):
        investor = get_object_or_404(Investor, pk=pk)
        relation_id = request.POST.get('relation_id') or None
        investor.relation_id = relation_id
        investor.save(update_fields=['relation_id'])
    return redirect(request.POST.get('next', 'crm:investors'))


@login_required
def investor_edit(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    investor = get_object_or_404(Investor, pk=pk)
    if request.method == 'POST':
        investor.name = request.POST.get('name', investor.name).strip()
        investor.type = request.POST.get('type', '')
        investor.country = request.POST.get('country', '').strip()
        investor.sectors = ', '.join(request.POST.getlist('sectors'))
        investor.areas = ', '.join(request.POST.getlist('areas'))
        investor.tipo_inversion = ', '.join(request.POST.getlist('tipo_inversion'))
        investor.inv_stage = ', '.join(request.POST.getlist('inv_stage'))
        investor.ticket_range = request.POST.get('ticket_range', '')
        investor.aum = request.POST.get('aum', '')
        investor.pub_status = request.POST.get('pub_status', '').strip()
        investor.relation_id = request.POST.get('relation') or None
        investor.notes = request.POST.get('notes', '').strip()
        investor.save()

        # Guardar contactos
        names  = request.POST.getlist('contact_name')
        roles  = request.POST.getlist('contact_role')
        emails = request.POST.getlist('contact_email')
        phones = request.POST.getlist('contact_phone')
        if request.user.role == 'admin':
            # Solo el admin puede eliminar contactos existentes
            investor.contacts.all().delete()
            for name, role, email, phone in zip(names, roles, emails, phones):
                if name.strip():
                    InvestorContact.objects.create(
                        investor=investor,
                        name=name.strip(), role=role.strip(),
                        email=email.strip(), phone=phone.strip(),
                    )
        else:
            # El resto solo puede añadir contactos nuevos (sin borrar los existentes)
            existing_ids = set(investor.contacts.values_list('pk', flat=True))
            ids_in_form  = [v for v in request.POST.getlist('contact_id') if v]
            for name, role, email, phone in zip(names, roles, emails, phones):
                if name.strip() and name.strip() not in [
                    c.name for c in investor.contacts.filter(pk__in=ids_in_form)
                ]:
                    InvestorContact.objects.get_or_create(
                        investor=investor, name=name.strip(),
                        defaults={'role': role.strip(), 'email': email.strip(), 'phone': phone.strip()},
                    )

        messages.success(request, 'Inversor actualizado.')
    return redirect('crm:investor_detail', pk=pk)


@login_required
def investor_log_create(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    investor = get_object_or_404(Investor, pk=pk)
    if request.method == 'POST':
        from crm.models import InvestorLog
        log_type = request.POST.get('type', 'Nota')
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f:
            slug = _re.sub(r'[^\w\-.]', '_', investor.name.strip())
            saved_path = _save_contact_doc(f, 'Inversores', investor.name)
            actual_filename = pathlib.Path(saved_path).name
            attachment_url = reverse('crm:docs_contactos_download',
                                     args=('inversores', slug, actual_filename))
        ctx = request.POST.get('context', '')
        from crm.models import ProcesoMA, Colaboracion as ColaboracionModel
        round_id   = request.POST.get('round_id') or None
        ma_id      = request.POST.get('proceso_ma_id') or None
        colab_id   = request.POST.get('colaboracion_id') or None
        InvestorLog.objects.create(
            investor=investor, type=log_type,
            date=request.POST.get('date') or None, summary=request.POST.get('summary', ''),
            created_by=request.user.get_full_name() or request.user.username,
            attachment_url=attachment_url, context=ctx,
            round_id=round_id if ctx == 'ronda' else None,
            proceso_ma_id=ma_id if ctx == 'ma' else None,
            colaboracion_id=colab_id if ctx == 'colaboracion' else None,
        )
        messages.success(request, 'Contacto registrado.')
    return redirect('crm:investor_detail', pk=investor.pk)


@login_required
def colaborador_log_create(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    colaborador = get_object_or_404(Colaborador, pk=pk)
    if request.method == 'POST':
        from crm.models import ColaboradorLog
        log_type = request.POST.get('type', 'Nota')
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f:
            slug = _re.sub(r'[^\w\-.]', '_', colaborador.name.strip())
            saved_path = _save_contact_doc(f, 'Colaboradores', colaborador.name)
            actual_filename = pathlib.Path(saved_path).name
            attachment_url = reverse('crm:docs_contactos_download',
                                     args=('colaboradores', slug, actual_filename))
        ctx = request.POST.get('context', '')
        from crm.models import ProcesoMA, Colaboracion as ColaboracionModel
        round_id  = request.POST.get('round_id') or None
        ma_id     = request.POST.get('proceso_ma_id') or None
        colab_id  = request.POST.get('colaboracion_id') or None
        ColaboradorLog.objects.create(
            colaborador=colaborador, type=log_type,
            date=request.POST.get('date') or None, summary=request.POST.get('summary', ''),
            created_by=request.user.get_full_name() or request.user.username,
            attachment_url=attachment_url, context=ctx,
            round_id=round_id if ctx == 'ronda' else None,
            proceso_ma_id=ma_id if ctx == 'ma' else None,
            colaboracion_id=colab_id if ctx == 'colaboracion' else None,
        )
        messages.success(request, 'Contacto registrado.')
    return redirect('crm:colaborador_detail', pk=colaborador.pk)


@login_required
def investor_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(InvestorLog, pk=pk)
    investor_pk = log.investor_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:investor_detail', pk=investor_pk)


@login_required
def interaction_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    interaction = get_object_or_404(Interaction, pk=pk)
    investor_pk = interaction.introduction.investor_id
    if request.method == 'POST':
        interaction.delete()
    return redirect('crm:investor_detail', pk=investor_pk)


@login_required
def investor_log_edit(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(InvestorLog, pk=pk)
    if request.method == 'POST':
        log.date    = request.POST.get('date') or None
        log.summary = request.POST.get('summary', '').strip()
        log.save(update_fields=['date', 'summary'])
    return redirect('crm:investor_detail', pk=log.investor_id)


@login_required
def colaborador_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(ColaboradorLog, pk=pk)
    colaborador_pk = log.colaborador_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:colaborador_detail', pk=colaborador_pk)


@login_required
def colaborador_log_edit(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(ColaboradorLog, pk=pk)
    if request.method == 'POST':
        log.date    = request.POST.get('date') or None
        log.summary = request.POST.get('summary', '').strip()
        log.save(update_fields=['date', 'summary'])
    return redirect('crm:colaborador_detail', pk=log.colaborador_id)


@login_required
def colaboracion_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    from crm.models import InteraccionColaboracion
    log = get_object_or_404(InteraccionColaboracion, pk=pk)
    col_pk = log.colaboracion_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:colaboracion_detail', pk=col_pk)


# ── Presentaciones ───────────────────────────────────────────────────────────

PRES_GROUP_KEYS = {
    'company':  lambda it: it.company.name,
    'investor': lambda it: it.investor.name,
    'round':    lambda it: it.round.type or '—',
    'status':   lambda it: it.status.nombre if it.status else '—',
}
PRES_GROUP_LABELS = [
    ('company', 'Participada'), ('investor', 'Inversor'),
    ('round', 'Ronda'), ('status', 'Estado'),
]


PRES_TERMINAL = ('Invertido', 'Descartado')


@login_required
def presentaciones_pipeline(request):
    from crm.utils import ESTADO_W
    companies = visible_companies(request.user)

    if request.method == 'POST' and can_edit(request.user):
        round_id = request.POST.get('round')
        contact_type = request.POST.get('contact_type', 'investor')
        investor_id = request.POST.get('investor') if contact_type == 'investor' else None
        colaborador_id = request.POST.get('colaborador') if contact_type == 'colaborador' else None
        if round_id and (investor_id or colaborador_id):
            r = get_object_or_404(Round, pk=round_id)
            if can_see_company(request.user, r.company_id):
                Introduction.objects.create(
                    round=r, company=r.company,
                    investor_id=investor_id or None,
                    colaborador_id=colaborador_id or None,
                    status_id=request.POST.get('status') or None,
                    ticket=request.POST.get('ticket') or None,
                    date=request.POST.get('date') or None,
                    intro_by=request.POST.get('intro_by', ''),
                    next_action=request.POST.get('next_action', ''),
                    next_date=request.POST.get('next_date') or None,
                    notes=request.POST.get('notes', ''),
                )
                messages.success(request, 'Presentación añadida.')
        return redirect('crm:presentaciones_pipeline')

    intros = visible_introductions(request.user).select_related(
        'company', 'round', 'investor', 'colaborador', 'status'
    )
    q = request.GET.get('q', '').strip()
    company_filter = request.GET.get('company', '')
    estado_filter = request.GET.get('estado', '')
    view = request.GET.get('view', 'kanban')
    if q:
        intros = intros.filter(
            models.Q(investor__name__icontains=q) | models.Q(colaborador__name__icontains=q) | models.Q(company__name__icontains=q)
        )
    if company_filter:
        intros = intros.filter(company_id=company_filter)
    if estado_filter:
        intros = intros.filter(status_id=estado_filter)

    intros = list(intros)
    estados = EstadoPresentacion.objects.all()

    pipe_stages, end_stages = [], []
    for estado in estados:
        items = [i for i in intros if i.status_id == estado.id]
        stage = {
            'estado': estado,
            'items': items,
            'total': sum(i.ticket or 0 for i in items),
            'peso': int(ESTADO_W.get(estado.nombre, 0) * 100),
        }
        if estado.nombre in PRES_TERMINAL:
            end_stages.append(stage)
        else:
            pipe_stages.append(stage)
    sin_estado = [i for i in intros if i.status_id is None]
    if sin_estado:
        pipe_stages.insert(0, {'estado': None, 'items': sin_estado, 'total': 0, 'peso': 0})

    all_rounds = Round.objects.filter(company__in=companies).select_related('company').order_by('company__name', 'type')

    g1, g2, g3 = _parse_groups(request.GET, PRES_GROUP_KEYS)
    keyfns = [PRES_GROUP_KEYS[k] for k in (g1, g2, g3) if k]
    groups = _build_groups(intros, keyfns) if keyfns else None

    return render(request, 'crm/presentaciones_pipeline.html', {
        'active_nav': 'pres_pipeline',
        'pipe_stages': pipe_stages, 'end_stages': end_stages,
        'q': q, 'company_filter': company_filter, 'estado_filter': estado_filter, 'view': view,
        'all_companies': companies.order_by('name'),
        'all_rounds': all_rounds,
        'all_investors': visible_investors(request.user).order_by('name'),
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'estados': estados,
        'intros_flat': intros,
        'groups': groups, 'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': PRES_GROUP_LABELS,
        'can_edit': can_edit(request.user),
    })


@login_required
def presentaciones(request):
    if request.method == 'POST' and can_edit(request.user):
        form = IntroductionForm(request.POST)
        _set_intro_form_querysets(form, request.user)
        if form.is_valid():
            intro = form.save(commit=False)
            intro.company = intro.round.company
            intro.save()
            messages.success(request, 'Presentación añadida correctamente.')
            return redirect('crm:presentaciones')
    else:
        form = IntroductionForm()
        _set_intro_form_querysets(form, request.user)

    intros = visible_introductions(request.user).select_related('company', 'round', 'investor', 'status')

    q = request.GET.get('q', '').strip()
    estado_id = request.GET.get('estado', '')

    if estado_id:
        intros = intros.filter(status_id=estado_id)
    if q:
        intros = intros.filter(
            models.Q(company__name__icontains=q)
            | models.Q(round__type__icontains=q)
            | models.Q(investor__name__icontains=q)
            | models.Q(intro_by__icontains=q)
            | models.Q(next_action__icontains=q)
        )

    intros = list(intros)

    g1, g2, g3 = _parse_groups(request.GET, PRES_GROUP_KEYS.keys())
    active_groups = [g for g in (g1, g2, g3) if g]
    groups = _build_groups(intros, [PRES_GROUP_KEYS[g] for g in active_groups]) if active_groups else None

    return render(request, 'crm/presentaciones.html', {
        'active_nav': 'presentaciones', 'intros': intros, 'groups': groups,
        'q': q, 'estado_id': estado_id,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': PRES_GROUP_LABELS,
        'estados': EstadoPresentacion.objects.all(),
        'form': form, 'can_edit': can_edit(request.user),
    })


def _set_intro_form_querysets(form, user):
    visible_ids = allowed_company_ids(user)
    form.fields['round'].queryset = (
        Round.objects.filter(company_id__in=visible_ids)
        .select_related('company')
        .order_by('company__name', 'type')
    )
    form.fields['investor'].queryset = visible_investors(user).order_by('name')


@login_required
def inbox_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    msg = get_object_or_404(InboxMessage, pk=pk)
    if request.method == 'POST':
        msg.delete()
        messages.success(request, 'Email eliminado.')
    return redirect('crm:inbox')


@login_required
def inbox(request):
    import json as _json
    ColabModel = Colaborador

    if request.method == 'POST':
        if not can_edit(request.user):
            return HttpResponseForbidden()
        msg    = get_object_or_404(InboxMessage, pk=request.POST.get('message_id'))
        summary      = request.POST.get('summary', '').strip()
        proceso_type = request.POST.get('proceso_type', '')   # 'round' | 'ma'
        proceso_id   = request.POST.get('proceso_id') or None
        contact_type = request.POST.get('contact_type', '')   # 'investor' | 'colaborador'
        contact_id   = request.POST.get('contact_id') or None

        if summary and contact_id:
            autor = 'Bandeja de entrada'
            if contact_type == 'investor':
                investor = get_object_or_404(Investor, pk=contact_id)
                msg.investor = investor
                if proceso_type == 'round' and proceso_id:
                    round_obj = get_object_or_404(Round, pk=proceso_id)
                    InvestorLog.objects.create(
                        investor=investor, date=msg.date, type='Email', summary=summary,
                        created_by=autor, context='ronda', round=round_obj,
                    )
                    msg.round = round_obj
                elif proceso_type == 'ma' and proceso_id:
                    proceso = get_object_or_404(ProcesoMA, pk=proceso_id)
                    InvestorLog.objects.create(
                        investor=investor, date=msg.date, type='Email', summary=summary,
                        created_by=autor, context='ma', proceso_ma=proceso,
                    )
                    msg.proceso_ma = proceso
                else:
                    InvestorLog.objects.create(
                        investor=investor, date=msg.date, type='Email', summary=summary, created_by=autor,
                    )
            elif contact_type == 'colaborador':
                colab = get_object_or_404(ColabModel, pk=contact_id)
                msg.colaborador = colab
                if proceso_type == 'ma' and proceso_id:
                    proceso = get_object_or_404(ProcesoMA, pk=proceso_id)
                    ColaboradorLog.objects.create(
                        colaborador=colab, date=msg.date, type='Email', summary=summary,
                        created_by=autor, context='ma', proceso_ma=proceso,
                    )
                    msg.proceso_ma = proceso
                elif proceso_type == 'round' and proceso_id:
                    round_obj = get_object_or_404(Round, pk=proceso_id)
                    ColaboradorLog.objects.create(
                        colaborador=colab, date=msg.date, type='Email', summary=summary,
                        created_by=autor, context='ronda', round=round_obj,
                    )
                    msg.round = round_obj
                else:
                    ColaboradorLog.objects.create(
                        colaborador=colab, date=msg.date, type='Email', summary=summary, created_by=autor,
                    )
        # ── Crear contacto nuevo si se solicitó ───────────────────────────────
        if request.POST.get('create_contact') == '1':
            nc_type      = request.POST.get('new_contact_type', '')
            nc_entity_id = request.POST.get('new_contact_entity_id') or None
            nc_name      = request.POST.get('new_contact_name', '').strip() or selected.from_name
            nc_role      = request.POST.get('new_contact_role', '').strip()
            nc_email     = selected.from_email
            if nc_type == 'investor' and nc_entity_id:
                inv = get_object_or_404(Investor, pk=nc_entity_id)
                InvestorContact.objects.get_or_create(
                    investor=inv, email=nc_email,
                    defaults={'name': nc_name, 'role': nc_role},
                )
            elif nc_type == 'colaborador' and nc_entity_id:
                colab = get_object_or_404(ColabModel, pk=nc_entity_id)
                ColaboradorContacto.objects.get_or_create(
                    colaborador=colab, email=nc_email,
                    defaults={'name': nc_name, 'role': nc_role},
                )

        msg.unread = False
        msg.saved  = True
        msg.save()
        messages.success(request, 'Email guardado en la cronología.')
        return redirect(f"{reverse('crm:inbox')}?id={msg.pk}")

    msgs = InboxMessage.objects.select_related('investor', 'colaborador', 'round', 'proceso_ma').all()
    sel_id   = request.GET.get('id')
    selected = None
    if sel_id:
        selected = get_object_or_404(InboxMessage, pk=sel_id)
    elif msgs:
        selected = msgs.first()

    matched_contact = None   # {'type': 'investor'|'colaborador', 'obj': <instance>, 'via': <email>}
    summary = ''
    companies_data  = []     # JSON para el JS cascading

    if selected:
        if selected.unread and not selected.saved:
            selected.unread = False
            selected.save(update_fields=['unread'])
        summary = (selected.subject or '').strip()

        # ── Buscar contacto por email ──────────────────────────────────────────
        if selected.from_email:
            email_lower = selected.from_email.lower()
            ic = InvestorContact.objects.filter(email__iexact=email_lower).select_related('investor').first()
            if ic:
                matched_contact = {'type': 'investor', 'obj': ic.investor, 'via': ic.email, 'label': ic.investor.name}
            else:
                cc = ColaboradorContacto.objects.filter(email__iexact=email_lower).select_related('colaborador').first()
                if cc:
                    matched_contact = {'type': 'colaborador', 'obj': cc.colaborador, 'via': cc.email, 'label': cc.colaborador.name}

        # ── Datos de participadas → procesos para JS ───────────────────────────
        for company in visible_companies(request.user):
            rounds = [{'id': r.pk, 'label': r.type}
                      for r in company.rounds.all()]
            procesos = [{'id': p.pk, 'label': p.nombre}
                        for p in company.procesos_ma.filter(cerrado=False)]
            if rounds or procesos:
                companies_data.append({'id': company.pk, 'name': company.name,
                                       'rounds': rounds, 'procesos': procesos})

    all_investors   = list(Investor.objects.order_by('name').values('id', 'name'))
    all_colaboradores = list(ColabModel.objects.order_by('name').values('id', 'name'))

    return render(request, 'crm/inbox.html', {
        'active_nav': 'inbox',
        'msgs': msgs,
        'selected': selected,
        'summary': summary,
        'matched_contact': matched_contact,
        'companies_json': _json.dumps(companies_data),
        'investors_json': _json.dumps(all_investors),
        'colaboradores_json': _json.dumps(all_colaboradores),
        'can_edit': can_edit(request.user),
    })


@login_required
def kpis_inversion(request):
    from decimal import Decimal as D
    companies = visible_companies(request.user)
    all_rounds = Round.objects.filter(company__in=companies).prefetch_related(
        'introductions__status', 'introductions__investor', 'company', 'status'
    )
    open_rounds  = [r for r in all_rounds if not r.status or r.status.nombre != 'Cerrada']
    closed_rounds = [r for r in all_rounds if r.status and r.status.nombre == 'Cerrada']

    def _agg(rounds):
        target    = sum(r.target or 0 for r in rounds)
        invertido = sum(round_invertido(r) for r in rounds)
        weighted  = sum(round_weighted(r) for r in rounds)
        desc_total = D(0); desc_count = 0
        pipe_total = D(0); pipe_count = 0
        inv_count  = 0
        for r in rounds:
            for i in r.introductions.all():
                nombre = i.status.nombre if i.status else ''
                t = i.ticket or D(0)
                if nombre == 'Invertido':
                    inv_count += 1
                elif nombre == 'Descartado':
                    desc_total += t; desc_count += 1
                elif nombre not in ('No contactado',):
                    pipe_total += t; pipe_count += 1
        return {
            'target': target, 'invertido': invertido, 'weighted': weighted,
            'pipe_total': pipe_total, 'pipe_count': pipe_count,
            'desc_total': desc_total, 'desc_count': desc_count,
            'inv_count': inv_count,
            'count': len(rounds),
            'companies': len({r.company_id for r in rounds}),
        }

    open_agg   = _agg(open_rounds)
    closed_agg = _agg(closed_rounds)

    # ── Datos por ronda para el gráfico de barras ────────────────────────────
    rounds_chart = []
    for r in open_rounds:
        inv  = round_invertido(r)
        pond = round_weighted(r)
        tgt  = r.target or D(0)
        pipe_no_pond = D(0)
        for i in r.introductions.all():
            nombre = i.status.nombre if i.status else ''
            if nombre not in ('Invertido', 'Descartado'):
                pipe_no_pond += i.ticket or D(0)
        activas = sum(1 for i in r.introductions.all()
                      if i.status and i.status.nombre not in ('Descartado', 'No contactado'))
        rounds_chart.append({
            'label': f'{r.company.name} · {r.type}',
            'invertido': float(inv),
            'ponderado': float(pond),
            'pipe_total': float(pipe_no_pond),
            'target': float(tgt),
            'pct_inv':  round(float(inv / tgt * 100), 1) if tgt else 0,
            'pct_pond': round(float(pond / tgt * 100), 1) if tgt else 0,
            'pct_pipe': round(float(pipe_no_pond / tgt * 100), 1) if tgt else 0,
            'activas': activas,
            'round': r,
        })

    # ── Presentaciones: embudo por estado ────────────────────────────────────
    estados_ep = list(EstadoPresentacion.objects.all())
    all_intros  = Introduction.objects.filter(round__in=open_rounds).select_related('status')
    total_all   = all_intros.count()
    activas_count = all_intros.exclude(status__nombre__in=['Descartado']).count()

    embudo = []
    for e in estados_ep:
        cnt = all_intros.filter(status=e).count()
        if cnt:
            embudo.append({'nombre': e.nombre, 'count': cnt,
                           'pct': round(cnt / activas_count * 100) if activas_count else 0})

    inv_total   = all_intros.filter(status__nombre='Invertido').count()
    desc_total  = all_intros.filter(status__nombre='Descartado').count()
    act_total   = total_all - desc_total

    # ── Rondas activas (lista con barra de progreso) ──────────────────────────
    rondas_activas = []
    for r in open_rounds:
        inv  = round_invertido(r)
        tgt  = r.target or D(0)
        fase = r.status.nombre if r.status else '—'
        pct  = min(int(inv / tgt * 100), 100) if tgt else 0
        rondas_activas.append({
            'round': r, 'invertido': inv, 'target': tgt, 'pct': pct, 'fase': fase,
        })

    return render(request, 'crm/kpis_inversion.html', {
        'active_nav': 'kpis_inversion',
        'open_agg': open_agg, 'closed_agg': closed_agg,
        'rounds_chart': rounds_chart,
        'embudo': embudo,
        'inv_total': inv_total, 'desc_total_pres': desc_total,
        'act_total': act_total, 'total_all': total_all,
        'rondas_activas': rondas_activas,
    })


@login_required
def kpis_ma(request):
    from decimal import Decimal as D
    companies = visible_companies(request.user)
    all_procesos = list(
        ProcesoMA.objects.filter(company__in=companies)
        .prefetch_related('contactos__status', 'company', 'fase')
    )
    abiertos  = [p for p in all_procesos if not p.cerrado]
    cerrados  = [p for p in all_procesos if p.cerrado]

    def _agg_ma(procesos):
        target   = sum(p.precio_pedido or 0 for p in procesos)
        vendido  = sum(proceso_ma_vendido(p) for p in procesos)
        weighted = sum(proceso_ma_weighted(p) for p in procesos)
        desc_total = D(0); desc_count = 0
        pipe_total = D(0); pipe_count = 0
        for p in procesos:
            for c in p.contactos.all():
                nombre = c.status.nombre if c.status else ''
                of = c.oferta_precio or D(0)
                if nombre == 'Vendido':
                    pass
                elif nombre == 'Descartado':
                    desc_total += of; desc_count += 1
                else:
                    pipe_total += of; pipe_count += 1
        return {
            'target': target, 'vendido': vendido, 'weighted': weighted,
            'pipe_total': pipe_total, 'pipe_count': pipe_count,
            'desc_total': desc_total, 'desc_count': desc_count,
            'count': len(procesos),
            'companies': len({p.company_id for p in procesos}),
        }

    open_agg   = _agg_ma(abiertos)
    closed_agg = _agg_ma(cerrados)

    # Datos por proceso para el gráfico de barras
    procesos_chart = []
    for p in abiertos:
        vend  = proceso_ma_vendido(p)
        pond  = proceso_ma_weighted(p)
        tgt   = p.precio_pedido or D(0)
        pipe_np = D(0)
        for c in p.contactos.all():
            nombre = c.status.nombre if c.status else ''
            if nombre not in ('Vendido', 'Descartado'):
                pipe_np += c.oferta_precio or D(0)
        activos = sum(1 for c in p.contactos.all()
                      if c.status and c.status.nombre not in ('Descartado', 'No contactado'))
        procesos_chart.append({
            'label': f'{p.company.name} · {p.nombre}',
            'vendido': float(vend), 'ponderado': float(pond),
            'pipe_total': float(pipe_np), 'target': float(tgt),
            'pct_vend':  round(float(vend / tgt * 100), 1) if tgt else 0,
            'pct_pond':  round(float(pond / tgt * 100), 1) if tgt else 0,
            'pct_pipe':  round(float(pipe_np / tgt * 100), 1) if tgt else 0,
            'activos': activos, 'proceso': p,
        })

    # Embudo por estado
    estados_ma_list = list(EstadoMA.objects.all())
    all_contactos = ContactoMA.objects.filter(proceso__in=abiertos).select_related('status')
    total_all  = all_contactos.count()
    act_total  = all_contactos.exclude(status__nombre='Descartado').count()
    vend_total = all_contactos.filter(status__nombre='Vendido').count()
    desc_total = all_contactos.filter(status__nombre='Descartado').count()
    embudo = []
    for e in estados_ma_list:
        cnt = all_contactos.filter(status=e).count()
        if cnt:
            embudo.append({'nombre': e.nombre, 'count': cnt,
                           'pct': round(cnt / act_total * 100) if act_total else 0})

    # Lista procesos abiertos con barra
    procesos_activos = []
    for p in abiertos:
        vend = proceso_ma_vendido(p)
        tgt  = p.precio_pedido or D(0)
        pct  = min(int(vend / tgt * 100), 100) if tgt else 0
        fase = p.fase.nombre if p.fase else '—'
        procesos_activos.append({'proceso': p, 'vendido': vend, 'target': tgt, 'pct': pct, 'fase': fase})

    return render(request, 'crm/kpis_ma.html', {
        'active_nav': 'kpis_ma',
        'open_agg': open_agg, 'closed_agg': closed_agg,
        'procesos_chart': procesos_chart,
        'embudo': embudo,
        'vend_total': vend_total, 'desc_total_c': desc_total,
        'act_total': act_total, 'total_all': total_all,
        'procesos_activos': procesos_activos,
    })


@login_required
def kpis_colaboraciones(request):
    from decimal import Decimal as D
    companies = visible_companies(request.user)
    all_colabs = list(
        Colaboracion.objects.filter(company__in=companies)
        .prefetch_related('status', 'company', 'colaborador', 'investor')
    )
    activas   = [c for c in all_colabs if c.status and c.status.nombre not in ('Descartado',)]
    cerradas  = [c for c in all_colabs if c.status and c.status.nombre == 'Descartado']

    # Conteos por tipo de relación
    from collections import Counter
    tipo_counts = Counter(c.tipo_relacion or 'Sin tipo' for c in all_colabs)

    # Conteos por estado para embudo
    estados_colab_list = list(EstadoColaboracion.objects.all())
    act_qs  = Colaboracion.objects.filter(company__in=companies).select_related('status', 'company', 'colaborador')
    act_count  = act_qs.exclude(status__nombre='Descartado').count()
    desc_count = act_qs.filter(status__nombre='Descartado').count()
    total_all  = act_qs.count()

    embudo = []
    for e in estados_colab_list:
        cnt = act_qs.filter(status=e).count()
        if cnt:
            embudo.append({'nombre': e.nombre, 'count': cnt,
                           'pct': round(cnt / act_count * 100) if act_count else 0})

    # Top colaboradores por nº de colaboraciones activas
    from crm.models import Colaborador
    top_colabs = []
    for col in Colaborador.objects.prefetch_related('colaboraciones__status', 'colaboraciones__company'):
        n_act = sum(1 for c in col.colaboraciones.all()
                    if not c.status or c.status.nombre != 'Descartado')
        if n_act:
            top_colabs.append({'colaborador': col, 'n_act': n_act,
                               'n_total': col.colaboraciones.count()})
    top_colabs.sort(key=lambda x: -x['n_act'])
    top_colabs = top_colabs[:10]

    # Participadas con más colaboraciones activas
    top_companies = []
    for comp in companies.prefetch_related('colaboraciones__status'):
        n = sum(1 for c in comp.colaboraciones.all()
                if not c.status or c.status.nombre != 'Descartado')
        if n:
            top_companies.append({'company': comp, 'n': n})
    top_companies.sort(key=lambda x: -x['n'])
    top_companies = top_companies[:8]

    # Colaboraciones recientes (últimas 10 activas por fecha)
    recientes = sorted(
        [c for c in all_colabs if not c.status or c.status.nombre != 'Descartado'],
        key=lambda c: c.date or __import__('datetime').date.min, reverse=True
    )[:10]

    return render(request, 'crm/kpis_colaboraciones.html', {
        'active_nav': 'kpis_colaboraciones',
        'total_activas': act_count, 'total_cerradas': desc_count, 'total_all': total_all,
        'total_colaboradores': len({c.colaborador_id for c in all_colabs if c.colaborador_id}),
        'total_participadas': len({c.company_id for c in all_colabs}),
        'embudo': embudo,
        'tipo_counts': dict(tipo_counts),
        'top_colabs': top_colabs,
        'top_companies': top_companies,
        'recientes': recientes,
        'act_count': act_count, 'desc_count': desc_count,
    })


@login_required
def tareas(request):
    from datetime import date as _date
    modulo = request.GET.get('modulo', 'inversion')
    companies = visible_companies(request.user)
    tareas = []

    if modulo == 'inversion':
        rounds = Round.objects.filter(company__in=companies).prefetch_related(
            'introductions__status', 'introductions__investor', 'company'
        )
        for r in rounds:
            for intro in r.introductions.all():
                if intro.next_action or intro.next_date:
                    tareas.append({
                        'next_date': intro.next_date,
                        'next_action': intro.next_action,
                        'contact_name': intro.investor.name if intro.investor else '—',
                        'entity_name': f'{r.company.name} · {r.type}',
                        'detail_url': ('crm:round_detail', r.pk),
                        'status': intro.status,
                    })
        # Relación con inversores
        ETAPA_ADVICE = {
            'Lead': 'Primer contacto / pedir intro',
            'Conocido': 'Construir relación, enviar updates',
            'Inversor no Activo': 'Reactivar con novedades de la cartera',
            'Relación activa': 'Mantener cadencia de contacto',
            'Coinversor no habitual': 'Proponer una coinversión concreta',
            'Coinversor habitual': 'Compartir deal flow prioritario',
            'Inversor estratégico': 'Implicar pronto · acceso preferente',
        }
        etapas = EtapaRelacion.objects.all()
        all_investors = visible_investors(request.user)
        total_inv = all_investors.count()
        relacion = []
        for e in etapas:
            cnt = all_investors.filter(relation=e).count()
            relacion.append({'etapa': e, 'count': cnt,
                             'pct': round(cnt / total_inv * 100) if total_inv else 0,
                             'advice': ETAPA_ADVICE.get(e.nombre, '')})
        sin_etapa = all_investors.filter(relation=None).count()
        if sin_etapa:
            relacion.insert(0, {'etapa': None, 'count': sin_etapa,
                                'pct': round(sin_etapa / total_inv * 100) if total_inv else 0,
                                'advice': ''})

    elif modulo == 'ma':
        procesos = ProcesoMA.objects.filter(company__in=companies, cerrado=False).prefetch_related(
            'contactos__status', 'company'
        )
        for p in procesos:
            for c in p.contactos.all():
                if c.next_action or c.next_date:
                    tareas.append({
                        'next_date': c.next_date,
                        'next_action': c.next_action,
                        'contact_name': c.contact.name if c.contact else '—',
                        'entity_name': f'{p.company.name} · {p.nombre}',
                        'detail_url': ('crm:proceso_ma_detail', p.pk),
                        'status': c.status,
                    })
        relacion = None

    elif modulo == 'colaboraciones':
        colabs = Colaboracion.objects.filter(company__in=companies).exclude(
            status__nombre='Descartado'
        ).prefetch_related('colaborador', 'investor', 'company', 'status')
        for c in colabs:
            if c.next_action or c.next_date:
                contact = c.colaborador or c.investor
                tareas.append({
                    'next_date': c.next_date,
                    'next_action': c.next_action,
                    'contact_name': contact.name if contact else '—',
                    'entity_name': f'{c.company.name}',
                    'detail_url': ('crm:colaboracion_detail', c.pk),
                    'status': c.status,
                })
        relacion = None

    tareas.sort(key=lambda x: x['next_date'] or _date.max)
    return render(request, 'crm/tareas.html', {
        'active_nav': 'tareas',
        'modulo': modulo,
        'tareas': tareas,
        'relacion': relacion if modulo == 'inversion' else None,
    })


@login_required
def comunicaciones(request):
    from datetime import date as _date
    modulo = request.GET.get('modulo', 'inversion')
    companies = visible_companies(request.user)
    entities = []
    selected_pk = request.GET.get('entity', '')
    selected_entity = None
    comms = []

    if modulo == 'inversion':
        entities = list(Round.objects.filter(company__in=companies).select_related('company').order_by('-start'))
        entity_label = lambda e: f'{e.company.name} · {e.type}'
        if selected_pk:
            selected_entity = get_object_or_404(Round, pk=selected_pk, company__in=companies)
            for intro in selected_entity.introductions.select_related('investor', 'status').prefetch_related('interactions'):
                if not intro.investor:
                    continue
                timeline = []
                for lg in intro.investor.logs.filter(round=selected_entity).order_by('-date'):
                    timeline.append({'date': lg.date, 'type': lg.type, 'summary': lg.summary})
                for it in intro.interactions.order_by('-date'):
                    timeline.append({'date': it.date, 'type': it.type, 'summary': it.note})
                timeline.sort(key=lambda x: x['date'] or _date.min, reverse=True)
                comms.append({'contact': intro.investor, 'status': intro.status, 'timeline': timeline,
                              'contact_type': intro.investor.type or ''})
        elif entities:
            return redirect(f"{request.path}?modulo={modulo}&entity={entities[0].pk}")

    elif modulo == 'ma':
        entities = list(ProcesoMA.objects.filter(company__in=companies, cerrado=False).select_related('company').order_by('-start'))
        entity_label = lambda e: f'{e.company.name} · {e.nombre}'
        if selected_pk:
            selected_entity = get_object_or_404(ProcesoMA, pk=selected_pk, company__in=companies)
            for c in selected_entity.contactos.select_related('comprador', 'investor', 'status').prefetch_related('interactions'):
                contact = c.comprador or c.investor
                if not contact:
                    continue
                timeline = []
                for it in c.interactions.order_by('-date'):
                    timeline.append({'date': it.date, 'type': it.type, 'summary': it.note})
                timeline.sort(key=lambda x: x['date'] or _date.min, reverse=True)
                comms.append({'contact': contact, 'status': c.status, 'timeline': timeline, 'contact_type': ''})
        elif entities:
            return redirect(f"{request.path}?modulo={modulo}&entity={entities[0].pk}")

    elif modulo == 'colaboraciones':
        entities = list(Colaboracion.objects.filter(company__in=companies).exclude(
            status__nombre='Descartado'
        ).select_related('colaborador', 'investor', 'company', 'status').prefetch_related('interactions').order_by('-date'))
        entity_label = lambda e: f'{(e.colaborador or e.investor or type("x", (), {"name": "—"})()).name} — {e.company.name}'
        if selected_pk:
            selected_entity = get_object_or_404(Colaboracion, pk=selected_pk, company__in=companies)
            contact = selected_entity.colaborador or selected_entity.investor
            timeline = []
            for it in selected_entity.interactions.order_by('-date'):
                timeline.append({'date': it.date, 'type': it.type, 'summary': it.note})
            comms = [{'contact': contact, 'status': selected_entity.status, 'timeline': timeline, 'contact_type': ''}]
        elif entities:
            return redirect(f"{request.path}?modulo={modulo}&entity={entities[0].pk}")

    entities_with_labels = [(e, entity_label(e)) for e in entities]
    return render(request, 'crm/comunicaciones.html', {
        'active_nav': 'comunicaciones',
        'modulo': modulo,
        'entities': entities_with_labels,
        'selected_pk': selected_pk,
        'selected_entity': selected_entity,
        'comms': comms,
    })


@login_required
def reports(request):
    return render(request, 'crm/placeholder.html', {'active_nav': 'reports', 'title': 'Informes'})


@login_required
def reports(request):
    companies = visible_companies(request.user)
    open_rounds = Round.objects.filter(company__in=companies).exclude(status__nombre='Cerrada')
    closed_rounds = Round.objects.filter(company__in=companies, status__nombre='Cerrada')

    def agg(rounds):
        intros = Introduction.objects.filter(round__in=rounds)
        invertido = sum(round_invertido(r) for r in rounds)
        weighted = sum(round_weighted(r) for r in rounds)
        pipe_total = sum(
            it.ticket or 0 for it in intros
            if it.status and it.status.nombre not in ('Invertido', 'Descartado', 'No contactado')
        )
        pipe_count = intros.exclude(status__nombre__in=['Invertido', 'Descartado', 'No contactado']).count()
        desc_total = sum(it.ticket or 0 for it in intros if it.status and it.status.nombre == 'Descartado')
        desc_count = intros.filter(status__nombre='Descartado').count()
        return {
            'target': sum(r.target or 0 for r in rounds),
            'invertido': invertido,
            'weighted': weighted,
            'pipe_total': pipe_total,
            'pipe_count': pipe_count,
            'desc_total': desc_total,
            'desc_count': desc_count,
            'count': rounds.count() if hasattr(rounds, 'count') else len(rounds),
        }

    open_agg = agg(open_rounds)
    closed_agg = agg(closed_rounds)

    comms_por_ronda = []
    for r in open_rounds:
        n = Interaction.objects.filter(introduction__round=r).count()
        comms_por_ronda.append({'round': r, 'count': n})
    comms_por_ronda.sort(key=lambda x: -x['count'])

    week_ago = timezone.now().date() - timedelta(days=7)
    contactados_semana = visible_investors(request.user).filter(
        models.Q(logs__date__gte=week_ago) | models.Q(introductions__interactions__date__gte=week_ago)
    ).distinct().count()

    return render(request, 'crm/reports.html', {
        'active_nav': 'reports', 'open_agg': open_agg, 'closed_agg': closed_agg,
        'companies_en_ronda': companies.filter(rounds__in=open_rounds).distinct().count(),
        'rondas_abiertas': open_rounds.count(),
        'comms_por_ronda': comms_por_ronda[:10],
        'contactados_semana': contactados_semana,
    })


@login_required
def users(request):
    if request.user.role != Role.ADMIN:
        return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form = UserForm(request.POST)
            if form.is_valid():
                u = form.save(commit=False)
                u.set_unusable_password()
                u.save()
                form.save_m2m()
                messages.success(request, 'Usuario creado.')
                return redirect('crm:users')
        else:
            u = get_object_or_404(User, pk=request.POST.get('user_id'))
            form = UserForm(request.POST, instance=u)
            if form.is_valid():
                form.save()
                messages.success(request, 'Usuario actualizado.')
                return redirect('crm:users')
        return render(request, 'crm/users.html', {
            'active_nav': 'users', 'users': User.objects.all(), 'form': form,
        })

    return render(request, 'crm/users.html', {
        'active_nav': 'users', 'users': User.objects.all(), 'form': UserForm(),
    })


# ─── Logs de fase (editar/borrar) ────────────────────────────────────────────

@login_required
def proceso_ma_fase_log_upd(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(ProcesoMAFaseLog, pk=pk)
    log.date    = request.POST.get('date') or log.date
    fase_id     = request.POST.get('fase_id')
    if fase_id:
        log.fase_id = int(fase_id)
    log.save(update_fields=['date', 'fase_id'])
    return redirect(reverse('crm:proceso_ma_edit', kwargs={'pk': log.proceso_id}))


@login_required
def proceso_ma_fase_log_del(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(ProcesoMAFaseLog, pk=pk)
    proceso_pk = log.proceso_id
    log.delete()
    return redirect(reverse('crm:proceso_ma_edit', kwargs={'pk': proceso_pk}))


@login_required
def round_fase_log_upd(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(RoundFaseLog, pk=pk)
    log.date    = request.POST.get('date') or log.date
    fase_id     = request.POST.get('fase_id')
    if fase_id:
        log.fase_id = int(fase_id)
    log.save(update_fields=['date', 'fase_id'])
    return redirect(reverse('crm:round_edit', kwargs={'pk': log.round_id}))


@login_required
def round_fase_log_del(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(RoundFaseLog, pk=pk)
    round_pk = log.round_id
    log.delete()
    return redirect(reverse('crm:round_edit', kwargs={'pk': round_pk}))


# ─── M&A ─────────────────────────────────────────────────────────────────────

@login_required
def proceso_ma_set_fase(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    from datetime import date as _date
    proceso = get_object_or_404(ProcesoMA.objects.select_related('company'), pk=pk)
    if not can_see_company(request.user, proceso.company_id):
        return HttpResponseForbidden()
    fase_id = request.POST.get('fase_id') or None
    proceso.fase_id = fase_id
    proceso.save(update_fields=['fase_id'])
    if fase_id:
        ProcesoMAFaseLog.objects.create(
            proceso=proceso, fase_id=fase_id,
            date=_date.today(),
            created_by=request.user.get_full_name() or request.user.username,
        )
    return redirect('crm:proceso_ma_detail', pk=pk)


@login_required
def round_set_fase(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    from datetime import date as _date
    r = get_object_or_404(Round.objects.select_related('company'), pk=pk)
    if not can_see_company(request.user, r.company_id):
        return HttpResponseForbidden()
    fase_id = request.POST.get('fase_id') or None
    r.status_id = fase_id
    r.save(update_fields=['status_id'])
    if fase_id:
        RoundFaseLog.objects.create(
            round=r, fase_id=fase_id,
            date=_date.today(),
            created_by=request.user.get_full_name() or request.user.username,
        )
    tab = request.POST.get('tab', 'matriz')
    return redirect(f"{reverse('crm:round_detail', kwargs={'pk': pk})}?tab={tab}")


@login_required
def proceso_ma_edit(request, pk):
    from datetime import date as _date
    proceso = get_object_or_404(ProcesoMA.objects.select_related('company'), pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, proceso.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        fase_anterior_id = proceso.fase_id
        form = ProcesoMAForm(request.POST, instance=proceso)
        if form.is_valid():
            form.save()
            if proceso.fase_id and proceso.fase_id != fase_anterior_id:
                ProcesoMAFaseLog.objects.create(
                    proceso=proceso, fase_id=proceso.fase_id,
                    date=_date.today(),
                    created_by=request.user.get_full_name() or request.user.username,
                )
            messages.success(request, 'Proceso M&A actualizado.')
            return redirect('crm:proceso_ma_detail', pk=proceso.pk)
    else:
        form = ProcesoMAForm(instance=proceso)
    return render(request, 'crm/proceso_ma_form.html', {
        'active_nav': 'companies', 'form': form, 'company': proceso.company,
        'title': f'Editar proceso M&A — {proceso.company.name}', 'proceso': proceso,
        'fase_logs': list(proceso.fase_logs.select_related('fase').order_by('date', 'pk')),
        'fases_ma': list(FaseMA.objects.order_by('orden')),
    })


@login_required
def proceso_ma_create(request, company_pk):
    from datetime import date as _date
    if not can_edit(request.user) or not can_see_company(request.user, company_pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        form = ProcesoMAForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.company = company
            p.save()
            if p.fase_id:
                ProcesoMAFaseLog.objects.create(
                    proceso=p, fase_id=p.fase_id,
                    date=_date.today(),
                    created_by=request.user.get_full_name() or request.user.username,
                )
            messages.success(request, 'Proceso M&A creado.')
            return redirect('crm:proceso_ma_detail', pk=p.pk)
    else:
        form = ProcesoMAForm()
    return render(request, 'crm/proceso_ma_form.html', {
        'active_nav': 'companies', 'form': form, 'company': company,
        'title': f'Nuevo proceso M&A — {company.name}',
    })


@login_required
def proceso_ma_detail(request, pk):
    proceso = get_object_or_404(ProcesoMA.objects.select_related('company'), pk=pk)
    if not can_see_company(request.user, proceso.company_id):
        return HttpResponseForbidden()

    tab = request.GET.get('tab', 'matriz')
    estados_ma = list(EstadoMA.objects.all())
    contactos = proceso.contactos.select_related('comprador', 'investor', 'status').all()

    q = request.GET.get('q', '').strip().lower()
    if q:
        contactos = [c for c in contactos if c.contact and q in str(c.contact).lower()]

    vendido_total = proceso_ma_vendido(proceso)
    weighted = proceso_ma_weighted(proceso)
    mejor_oferta = max((c.oferta_precio or 0 for c in proceso.contactos.all()), default=0)

    pipe_stages = [e for e in estados_ma if e.nombre not in MA_TERMINAL]
    end_stages = [e for e in estados_ma if e.nombre in MA_TERMINAL]

    def stage_data(stage):
        items = [c for c in contactos if c.status_id == stage.id]
        return {
            'estado': stage,
            'items': items,
            'total': sum(c.oferta_precio or 0 for c in items),
            'peso': int(MA_ESTADO_W.get(stage.nombre, 0) * 100),
        }

    kpis = {
        'precio_pedido': proceso.precio_pedido or 0,
        'mejor_oferta': mejor_oferta,
        'weighted': weighted,
        'vendido': vendido_total,
        'total_count': proceso.contactos.count(),
        'vendido_count': proceso.contactos.filter(status__nombre='Vendido').count(),
        'desc_count': proceso.contactos.filter(status__nombre='Descartado').count(),
        'pipe_count': proceso.contactos.exclude(status__nombre__in=MA_TERMINAL).count(),
    }

    if request.method == 'POST' and can_edit(request.user):
        contact_type = request.POST.get('contact_type', 'colaborador')
        comprador_id = request.POST.get('comprador') if contact_type == 'colaborador' else None
        investor_id = request.POST.get('investor') if contact_type == 'investor' else None
        status_id = request.POST.get('status') or None
        raw_oferta = (request.POST.get('oferta_precio') or '').replace('.', '').replace(',', '.')
        oferta = raw_oferta or None
        date = request.POST.get('date') or None
        intro_by = request.POST.get('intro_by', '')
        next_action = request.POST.get('next_action', '')
        next_date = request.POST.get('next_date') or None
        notes = request.POST.get('notes', '')
        if comprador_id or investor_id:
            ContactoMA.objects.create(
                proceso=proceso,
                comprador_id=comprador_id or None,
                investor_id=investor_id or None,
                status_id=status_id,
                oferta_precio=oferta,
                date=date, intro_by=intro_by,
                next_action=next_action, next_date=next_date, notes=notes,
            )
            messages.success(request, 'Contacto añadido.')
        return redirect('crm:proceso_ma_detail', pk=pk)

    all_colaboradores_ma = Colaborador.objects.order_by('name')
    all_investors_ma = visible_investors(request.user).order_by('name')

    fases_ma = list(FaseMA.objects.order_by('orden'))
    # Fechas por fase (todas las visitas)
    from collections import defaultdict
    _fase_dates: dict = defaultdict(list)
    for log in proceso.fase_logs.order_by('date', 'pk'):
        _fase_dates[log.fase_id].append(log.date)
    return render(request, 'crm/proceso_ma_detail.html', {
        'active_nav': 'companies',
        'proceso': proceso, 'company': proceso.company,
        'kpis': kpis, 'tab': tab, 'q': request.GET.get('q', ''),
        'contactos': contactos,
        'pipe_stages': [stage_data(s) for s in pipe_stages],
        'end_stages': [stage_data(s) for s in end_stages],
        'all_colaboradores': all_colaboradores_ma,
        'all_investors': all_investors_ma,
        'can_edit': can_edit(request.user),
        'estados_ma': estados_ma,
        'fases_ma': fases_ma,
        'fase_dates': dict(_fase_dates),
    })


@login_required
def contacto_ma_set_status(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    contacto = get_object_or_404(ContactoMA, pk=pk)
    if not can_see_company(request.user, contacto.proceso.company_id):
        return HttpResponseForbidden()
    estado = get_object_or_404(EstadoMA, pk=request.POST.get('estado_id'))
    estado_anterior = contacto.status.nombre if contacto.status else '—'
    contacto.status = estado
    contacto.save(update_fields=['status'])

    # Registrar cambio de estado en la cronología del inversor/colaborador
    from datetime import date as _date
    autor = request.user.get_full_name() or request.user.username
    proceso = contacto.proceso
    nota = f'Estado actualizado: {estado_anterior} → {estado.nombre} (M&A {proceso.nombre} · {proceso.company.name})'
    if contacto.investor_id:
        InvestorLog.objects.create(
            investor_id=contacto.investor_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='ma', proceso_ma_id=contacto.proceso_id,
        )
    elif contacto.comprador_id:
        from crm.models import ColaboradorLog
        ColaboradorLog.objects.create(
            colaborador_id=contacto.comprador_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='ma', proceso_ma_id=contacto.proceso_id,
        )

    return redirect(reverse('crm:proceso_ma_detail', kwargs={'pk': contacto.proceso_id}) + '?tab=pipeline')


@login_required
def contacto_ma_edit(request, pk):
    from crm.models import ContactoMA
    contacto = get_object_or_404(ContactoMA.objects.select_related('proceso__company'), pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, contacto.proceso.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        tab = request.POST.get('tab', 'matriz')
        contacto.status_id    = request.POST.get('status') or contacto.status_id
        raw_oferta = request.POST.get('oferta_precio') or ''
        contacto.oferta_precio = raw_oferta.replace('.', '').replace(',', '.') or None
        contacto.date         = request.POST.get('date') or None
        contacto.intro_by     = request.POST.get('intro_by', '')
        contacto.next_action  = request.POST.get('next_action', '')
        contacto.next_date    = request.POST.get('next_date') or None
        contacto.save(update_fields=['status', 'oferta_precio',
                                     'date', 'intro_by', 'next_action', 'next_date'])
        messages.success(request, 'Contacto actualizado.')
        return redirect(reverse('crm:proceso_ma_detail', kwargs={'pk': contacto.proceso_id}) + f'?tab={tab}')
    return HttpResponseForbidden()


@login_required
def contacto_ma_chrono(request, pk):
    from crm.models import ContactoMA, ColaboradorLog
    contacto = get_object_or_404(ContactoMA.objects.select_related('proceso__company', 'investor', 'comprador'), pk=pk)
    if not can_see_company(request.user, contacto.proceso.company_id):
        return HttpResponseForbidden()

    proceso = contacto.proceso
    proceso_label = f'{proceso.nombre} · {proceso.company.name}'

    if request.method == 'POST':
        if not can_edit(request.user):
            return JsonResponse({'ok': False}, status=403)
        from datetime import date as _date
        log_type = request.POST.get('type', 'Nota')
        summary  = request.POST.get('summary', '').strip()
        log_date = request.POST.get('date') or None
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f:
            if contacto.investor_id:
                saved = _save_contact_doc(f, 'Inversores', contacto.investor.name)
                slug = _re.sub(r'[^\w\-.]', '_', contacto.investor.name.strip())
                attachment_url = reverse('crm:docs_contactos_download',
                                         args=('inversores', slug, pathlib.Path(saved).name))
            elif contacto.comprador_id:
                saved = _save_contact_doc(f, 'Colaboradores', contacto.comprador.name)
                slug = _re.sub(r'[^\w\-.]', '_', contacto.comprador.name.strip())
                attachment_url = reverse('crm:docs_contactos_download',
                                         args=('colaboradores', slug, pathlib.Path(saved).name))
        if contacto.investor_id:
            InvestorLog.objects.create(
                investor_id=contacto.investor_id,
                type=log_type, date=log_date or _date.today(),
                summary=summary,
                created_by=request.user.get_full_name() or request.user.username,
                context='ma', proceso_ma_id=proceso.pk,
                attachment_url=attachment_url,
            )
        elif contacto.comprador_id:
            ColaboradorLog.objects.create(
                colaborador_id=contacto.comprador_id,
                type=log_type, date=log_date or _date.today(),
                summary=summary,
                created_by=request.user.get_full_name() or request.user.username,
                context='ma', proceso_ma_id=proceso.pk,
                attachment_url=attachment_url,
            )
        return JsonResponse({'ok': True})

    # GET: devolver logs
    from django.db.models import Q
    if contacto.investor_id:
        logs = list(InvestorLog.objects.filter(
            Q(investor_id=contacto.investor_id, proceso_ma_id=proceso.pk) |
            Q(investor_id=contacto.investor_id, type='Estado',
              summary__icontains=proceso.company.name, proceso_ma__isnull=True)
        ).order_by('-date', '-pk'))
    elif contacto.comprador_id:
        logs = list(ColaboradorLog.objects.filter(
            Q(colaborador_id=contacto.comprador_id, proceso_ma_id=proceso.pk) |
            Q(colaborador_id=contacto.comprador_id, type='Estado',
              summary__icontains=proceso.company.name, proceso_ma__isnull=True)
        ).order_by('-date', '-pk'))
    else:
        logs = []

    data = [{'date': (l.date.strftime('%d %b %Y') if l.date else '—'),
             'type': l.type, 'summary': l.summary or ''} for l in logs]
    return JsonResponse({'logs': data, 'proceso': proceso_label})


@login_required
def presentaciones_ma(request):
    companies = visible_companies(request.user)
    qs = ContactoMA.objects.filter(
        proceso__company__in=companies
    ).select_related('proceso__company', 'comprador', 'status')

    q = request.GET.get('q', '').strip()
    estado_id = request.GET.get('estado', '')

    if request.method == 'POST' and can_edit(request.user):
        proceso_id = request.POST.get('proceso')
        comprador_id = request.POST.get('comprador')
        if proceso_id and comprador_id:
            proceso_obj = get_object_or_404(ProcesoMA, pk=proceso_id, company__in=companies)
            comprador_obj = get_object_or_404(Comprador, pk=comprador_id)
            ContactoMA.objects.create(
                proceso=proceso_obj, comprador=comprador_obj,
                status_id=request.POST.get('status') or None,
                oferta_precio=request.POST.get('oferta_precio') or None,
                date=request.POST.get('date') or None,
                intro_by=request.POST.get('intro_by', ''),
                next_action=request.POST.get('next_action', ''),
                next_date=request.POST.get('next_date') or None,
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, 'Presentación M&A creada.')
        return redirect('crm:presentaciones_ma')

    if q:
        qs = qs.filter(
            models.Q(comprador__name__icontains=q)
            | models.Q(proceso__nombre__icontains=q)
            | models.Q(proceso__company__name__icontains=q)
            | models.Q(intro_by__icontains=q)
        )
    if estado_id:
        qs = qs.filter(status_id=estado_id)


    contactos = list(qs)

    MA_GRP_KEYS = {
        'company':   lambda c: c.proceso.company.name,
        'proceso':   lambda c: c.proceso.nombre,
        'comprador': lambda c: c.comprador.name,
        'estado':    lambda c: c.status.nombre if c.status else '—',
    }
    MA_GRP_LABELS = [
        ('company', 'Participada'), ('proceso', 'Proceso'),
        ('comprador', 'Comprador'), ('estado', 'Estado'),
    ]

    g1, g2, g3 = _parse_groups(request.GET, MA_GRP_KEYS.keys())
    active_g = [g for g in (g1, g2, g3) if g]
    groups = _build_groups(contactos, [MA_GRP_KEYS[g] for g in active_g]) if active_g else None

    all_procesos = ProcesoMA.objects.filter(company__in=companies).select_related('company').order_by('company__name', 'nombre')
    all_compradores = Colaborador.objects.filter(es_comprador=True).order_by('name')
    estados_ma = EstadoMA.objects.all()

    return render(request, 'crm/presentaciones_ma.html', {
        'active_nav': 'presentaciones_ma',
        'contactos': contactos, 'groups': groups,
        'q': q, 'estado_id': estado_id,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': MA_GRP_LABELS,
        'estados_ma': estados_ma,
        'all_procesos': all_procesos,
        'all_compradores': all_compradores,
        'can_edit': can_edit(request.user),
    })


@login_required
def procesos_ma_global(request):
    companies = visible_companies(request.user)
    q = request.GET.get('q', '').strip()
    cerrado = request.GET.get('cerrado', '')
    estado_id = request.GET.get('estado', '')
    company_filter = request.GET.get('company', '')
    view = request.GET.get('view', 'kanban')

    if request.method == 'POST' and can_edit(request.user):
        proceso_id = request.POST.get('proceso')
        contact_type = request.POST.get('contact_type', 'colaborador')
        comprador_id = request.POST.get('comprador') if contact_type == 'colaborador' else None
        investor_id = request.POST.get('investor') if contact_type == 'investor' else None
        if proceso_id and (comprador_id or investor_id):
            proceso = get_object_or_404(ProcesoMA, pk=proceso_id)
            if can_see_company(request.user, proceso.company_id):
                ContactoMA.objects.create(
                    proceso=proceso,
                    comprador_id=comprador_id or None,
                    investor_id=investor_id or None,
                    status_id=request.POST.get('status') or None,
                    oferta_precio=request.POST.get('oferta_precio') or None,
                    date=request.POST.get('date') or None,
                    intro_by=request.POST.get('intro_by', ''),
                    next_action=request.POST.get('next_action', ''),
                    next_date=request.POST.get('next_date') or None,
                    notes=request.POST.get('notes', ''),
                )
                messages.success(request, 'Contacto M&A añadido.')
        return redirect('crm:procesos_ma_global')

    qs = ProcesoMA.objects.filter(company__in=companies).select_related('company').prefetch_related('contactos__status')
    if q:
        qs = qs.filter(models.Q(nombre__icontains=q) | models.Q(company__name__icontains=q))
    if cerrado == '1':
        qs = qs.filter(cerrado=True)
    elif cerrado == '0':
        qs = qs.filter(cerrado=False)
    procesos = list(qs.order_by('company__name', 'nombre'))

    # ContactoMA — usados tanto en kanban como en lista
    contactos_qs = ContactoMA.objects.filter(
        proceso__company__in=companies
    ).select_related('proceso__company', 'comprador', 'investor', 'status').order_by('proceso__company__name', 'proceso__nombre')
    if q:
        contactos_qs = contactos_qs.filter(
            models.Q(proceso__company__name__icontains=q) | models.Q(proceso__nombre__icontains=q)
            | models.Q(comprador__name__icontains=q) | models.Q(investor__name__icontains=q)
        )
    if estado_id:
        contactos_qs = contactos_qs.filter(status_id=estado_id)
    if company_filter:
        contactos_qs = contactos_qs.filter(proceso__company_id=company_filter)
    contactos_all = list(contactos_qs)
    estados_ma = list(EstadoMA.objects.all())

    pipe_stages_k, end_stages_k = [], []
    for estado in estados_ma:
        items = [c for c in contactos_all if c.status_id == estado.id]
        stage = {'estado': estado, 'items': items,
                 'total': sum(c.oferta_precio or 0 for c in items),
                 'peso': int(MA_ESTADO_W.get(estado.nombre, 0) * 100)}
        if estado.nombre in MA_TERMINAL:
            end_stages_k.append(stage)
        else:
            pipe_stages_k.append(stage)
    sin_estado_k = [c for c in contactos_all if c.status_id is None]
    if sin_estado_k:
        pipe_stages_k.insert(0, {'estado': None, 'items': sin_estado_k, 'total': 0, 'peso': 0})

    all_procesos = ProcesoMA.objects.filter(company__in=companies).select_related('company').order_by('company__name', 'nombre')
    ma_companies = companies.filter(procesos_ma__isnull=False).distinct().order_by('name')
    estados_ma_all = EstadoMA.objects.all()

    # Grouping for list view (ContactoMA)
    g1, g2, g3 = _parse_groups(request.GET, MA_CONTACTO_GROUP_KEYS)
    keyfns = [MA_CONTACTO_GROUP_KEYS[k] for k in (g1, g2, g3) if k]
    groups = _build_groups(contactos_all, keyfns) if keyfns else None

    return render(request, 'crm/procesos_ma_global.html', {
        'active_nav': 'ma_pipeline', 'procesos': procesos,
        'contactos_list': contactos_all,
        'q': q, 'cerrado': cerrado, 'estado_id': estado_id, 'company_filter': company_filter, 'view': view,
        'pipe_stages_k': pipe_stages_k, 'end_stages_k': end_stages_k,
        'all_procesos': all_procesos, 'ma_companies': ma_companies,
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'all_investors': visible_investors(request.user).order_by('name'),
        'estados_ma': estados_ma_all,
        'groups': groups, 'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': MA_CONTACTO_GROUP_LABELS,
        'can_edit': can_edit(request.user),
    })


@login_required
def compradores(request):
    return redirect('/colaboradores/?tipo=comprador')


@login_required
def comprador_detail(request, pk):
    return redirect('crm:colaborador_detail', pk=pk)


# ─── Colaboraciones ───────────────────────────────────────────────────────────

@login_required
def colaboracion_set_status(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    col = get_object_or_404(Colaboracion.objects.select_related('status', 'colaborador', 'company'), pk=pk)
    if not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()
    estado_id = request.POST.get('estado_id')
    estado_anterior = col.status.nombre if col.status else '—'
    col.status_id = estado_id or None
    col.save(update_fields=['status'])

    # Registrar cambio de estado en la cronología del colaborador y en la colaboración
    from datetime import date as _date
    from crm.models import ColaboradorLog, InteraccionColaboracion, EstadoColaboracion
    autor = request.user.get_full_name() or request.user.username
    nuevo_estado = EstadoColaboracion.objects.filter(pk=estado_id).first()
    nuevo_nombre = nuevo_estado.nombre if nuevo_estado else '—'
    nota = f'Estado actualizado: {estado_anterior} → {nuevo_nombre} ({col.company.name})'

    if col.colaborador_id:
        ColaboradorLog.objects.create(
            colaborador_id=col.colaborador_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='colaboracion', colaboracion=col,
        )
    elif col.investor_id:
        InvestorLog.objects.create(
            investor_id=col.investor_id,
            date=_date.today(), type='Estado',
            summary=nota, created_by=autor,
            context='colaboracion', colaboracion=col,
        )

    next_url = request.POST.get('next', '')
    if next_url == 'pipeline':
        return redirect('crm:colaboraciones_pipeline')
    return redirect('crm:company_detail', pk=col.company_id)


@login_required
def colaboraciones_pipeline(request):
    companies = visible_companies(request.user)
    qs = Colaboracion.objects.filter(company__in=companies).select_related('company', 'colaborador', 'investor', 'status')

    q = request.GET.get('q', '').strip()
    company_filter = request.GET.get('company', '')
    estado_filter = request.GET.get('estado', '')
    view = request.GET.get('view', 'kanban')

    if request.method == 'POST' and can_edit(request.user):
        company_id = request.POST.get('company')
        contact_type = request.POST.get('contact_type', 'colaborador')
        colaborador_id = request.POST.get('colaborador') if contact_type == 'colaborador' else None
        investor_id = request.POST.get('investor') if contact_type == 'investor' else None
        if company_id and (colaborador_id or investor_id):
            company_obj = get_object_or_404(Company, pk=company_id, id__in=companies.values_list('id', flat=True))
            Colaboracion.objects.create(
                company=company_obj,
                colaborador_id=colaborador_id or None,
                investor_id=investor_id or None,
                tipo_relacion=request.POST.get('tipo_relacion', ''),
                status_id=request.POST.get('status') or None,
                descripcion=request.POST.get('descripcion', ''),
                date=request.POST.get('date') or None,
                intro_by=request.POST.get('intro_by', ''),
                next_action=request.POST.get('next_action', ''),
                next_date=request.POST.get('next_date') or None,
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, 'Colaboración creada.')
        return redirect('crm:colaboraciones_pipeline')

    if q:
        qs = qs.filter(
            models.Q(colaborador__name__icontains=q)
            | models.Q(investor__name__icontains=q)
            | models.Q(company__name__icontains=q)
        )
    if company_filter:
        qs = qs.filter(company_id=company_filter)
    if estado_filter:
        qs = qs.filter(status_id=estado_filter)

    colaboraciones = list(qs)
    estados_all = EstadoColaboracion.objects.all()

    pipe_stages, end_stages = [], []
    for estado in estados_all:
        items = [c for c in colaboraciones if c.status_id == estado.id]
        stage = {'estado': estado, 'items': items}
        if estado.nombre in COLLAB_TERMINAL:
            end_stages.append(stage)
        else:
            pipe_stages.append(stage)
    sin_estado = [c for c in colaboraciones if c.status_id is None]
    if sin_estado:
        pipe_stages.insert(0, {'estado': None, 'items': sin_estado})

    g1, g2, g3 = _parse_groups(request.GET, COLAB_PIPE_GROUP_KEYS)
    keyfns = [COLAB_PIPE_GROUP_KEYS[k] for k in (g1, g2, g3) if k]
    groups = _build_groups(colaboraciones, keyfns) if keyfns else None

    return render(request, 'crm/colaboraciones_pipeline.html', {
        'active_nav': 'colaboraciones',
        'pipe_stages': pipe_stages, 'end_stages': end_stages,
        'q': q, 'company_filter': company_filter, 'estado_filter': estado_filter, 'view': view,
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'all_investors': visible_investors(request.user).order_by('name'),
        'all_companies': companies.order_by('name'),
        'estados_colab': estados_all,
        'colaboraciones_flat': colaboraciones,
        'groups': groups, 'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': COLAB_PIPE_GROUP_LABELS,
        'can_edit': can_edit(request.user),
    })


@login_required
def colaboraciones_global(request):
    companies = visible_companies(request.user)
    qs = Colaboracion.objects.filter(company__in=companies).select_related('company', 'colaborador', 'status')

    q = request.GET.get('q', '').strip()
    estado_id = request.GET.get('estado', '')

    if request.method == 'POST' and can_edit(request.user):
        company_id = request.POST.get('company')
        colaborador_id = request.POST.get('colaborador')
        if company_id and colaborador_id:
            from crm.models import Colaborador as ColabModel
            company_obj = get_object_or_404(Company, pk=company_id, id__in=companies.values_list('id', flat=True))
            colabobj = get_object_or_404(ColabModel, pk=colaborador_id)
            Colaboracion.objects.create(
                company=company_obj, colaborador=colabobj,
                tipo_relacion=request.POST.get('tipo_relacion', ''),
                status_id=request.POST.get('status') or None,
                descripcion=request.POST.get('descripcion', ''),
                date=request.POST.get('date') or None,
                intro_by=request.POST.get('intro_by', ''),
                next_action=request.POST.get('next_action', ''),
                next_date=request.POST.get('next_date') or None,
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, 'Presentación de colaboración creada.')
        return redirect('crm:colaboraciones')

    if q:
        qs = qs.filter(
            models.Q(colaborador__name__icontains=q)
            | models.Q(company__name__icontains=q)
            | models.Q(descripcion__icontains=q)
        )
    if estado_id:
        qs = qs.filter(status_id=estado_id)

    COL_GRP_KEYS = {
        'company':     lambda c: c.company.name,
        'colaborador': lambda c: c.colaborador.name,
        'tipo':        lambda c: c.tipo_relacion or '—',
        'estado':      lambda c: c.status.nombre if c.status else '—',
    }
    COL_GRP_LABELS = [
        ('company', 'Participada'), ('colaborador', 'Colaborador'),
        ('tipo', 'Tipo'), ('estado', 'Estado'),
    ]

    g1, g2, g3 = _parse_groups(request.GET, COL_GRP_KEYS.keys())
    active_g = [g for g in (g1, g2, g3) if g]
    colaboraciones = list(qs)
    groups = _build_groups(colaboraciones, [COL_GRP_KEYS[g] for g in active_g]) if active_g else None

    from crm.models import Colaborador as ColabModel
    all_colaboradores = ColabModel.objects.order_by('name')
    all_companies = companies.order_by('name')

    return render(request, 'crm/colaboraciones_global.html', {
        'active_nav': 'colaboraciones',
        'colaboraciones': colaboraciones, 'groups': groups,
        'q': q, 'estado_id': estado_id,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': COL_GRP_LABELS,
        'estados': EstadoColaboracion.objects.all(),
        'all_colaboradores': all_colaboradores,
        'all_companies': all_companies,
        'can_edit': can_edit(request.user),
    })


@login_required
def colaboracion_edit(request, pk):
    col = get_object_or_404(Colaboracion.objects.select_related('company', 'colaborador'), pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = ColaboracionForm(request.POST, instance=col)
        if form.is_valid():
            form.save()
            messages.success(request, 'Colaboración actualizada.')
            return redirect('crm:colaboracion_detail', pk=col.pk)
    else:
        form = ColaboracionForm(instance=col)
    return render(request, 'crm/colaboracion_form.html', {
        'active_nav': 'companies', 'form': form, 'company': col.company,
        'title': f'Editar colaboración — {col.colaborador.name if col.colaborador else col.company.name}',
        'colaboracion': col,
    })


@login_required
def colaboracion_create(request, company_pk):
    if not can_edit(request.user) or not can_see_company(request.user, company_pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        form = ColaboracionForm(request.POST)
        if form.is_valid():
            col = form.save(commit=False)
            col.company = company
            col.save()
            messages.success(request, 'Colaboración creada.')
            return redirect('crm:colaboracion_detail', pk=col.pk)
    else:
        form = ColaboracionForm()
    return render(request, 'crm/colaboracion_form.html', {
        'active_nav': 'companies', 'form': form, 'company': company,
        'title': f'Nueva colaboración — {company.name}',
    })


@login_required
def colaboracion_detail(request, pk):
    col = get_object_or_404(Colaboracion.objects.select_related('company', 'colaborador', 'status'), pk=pk)
    if not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()

    from crm.models import ColaboradorLog, EstadoColaboracion
    from datetime import date as _date

    if request.method == 'POST' and can_edit(request.user):
        log_type = request.POST.get('type', 'Nota')
        summary  = request.POST.get('summary', '')
        log_date = request.POST.get('date') or None
        autor    = request.user.get_full_name() or request.user.username
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f and col.colaborador_id:
            slug = _re.sub(r'[^\w\-.]', '_', col.colaborador.name.strip())
            saved_path = _save_contact_doc(f, 'Colaboradores', col.colaborador.name)
            actual_filename = pathlib.Path(saved_path).name
            attachment_url = reverse('crm:docs_contactos_download',
                                     args=('colaboradores', slug, actual_filename))
        elif f and col.investor_id:
            slug = _re.sub(r'[^\w\-.]', '_', col.investor.name.strip())
            saved_path = _save_contact_doc(f, 'Inversores', col.investor.name)
            actual_filename = pathlib.Path(saved_path).name
            attachment_url = reverse('crm:docs_contactos_download',
                                     args=('inversores', slug, actual_filename))
        if col.colaborador_id:
            ColaboradorLog.objects.create(
                colaborador=col.colaborador,
                date=log_date or _date.today(),
                type=log_type, summary=summary,
                created_by=autor,
                context='colaboracion', colaboracion=col,
                attachment_url=attachment_url,
            )
        elif col.investor_id:
            InvestorLog.objects.create(
                investor=col.investor,
                date=log_date or _date.today(),
                type=log_type, summary=summary,
                created_by=autor,
                context='colaboracion', colaboracion=col,
                attachment_url=attachment_url,
            )
        messages.success(request, 'Interacción registrada.')
        return redirect('crm:colaboracion_detail', pk=pk)

    # Cronología rica: ColaboradorLog + InvestorLog + InteraccionColaboracion heredada
    colab_logs = list(ColaboradorLog.objects.filter(colaboracion=col)
                      .order_by('-date', '-pk'))
    inv_logs   = list(InvestorLog.objects.filter(colaboracion=col)
                      .order_by('-date', '-pk'))
    legacy_logs = list(col.interactions.order_by('-date', '-pk'))
    # Evitar duplicados: si hay ColaboradorLog con mismo summary+date que una InteraccionColaboracion, omitir la legacy
    rich_keys = {(l.date, (l.summary or '').strip()) for l in colab_logs + inv_logs}
    chrono_rich = (
        [{'obj': l, 'kind': 'colab'} for l in colab_logs] +
        [{'obj': l, 'kind': 'inv'}   for l in inv_logs] +
        [{'obj': ic, 'kind': 'legacy'} for ic in legacy_logs
         if (ic.date, (ic.note or '').strip()) not in rich_keys]
    )
    chrono_rich.sort(key=lambda e: (e['obj'].date or _date.min), reverse=True)

    return render(request, 'crm/colaboracion_detail.html', {
        'active_nav': 'colaboraciones', 'col': col,
        'chrono_rich': chrono_rich,
        'can_edit': can_edit(request.user),
        'estados_col': list(EstadoColaboracion.objects.order_by('orden')),
    })


@login_required
def colaboracion_log_del(request, pk):
    """Borra un ColaboradorLog o InvestorLog y redirige a la colaboración."""
    from crm.models import ColaboradorLog
    if not can_edit(request.user) or request.method != 'POST':
        return HttpResponseForbidden()
    kind = request.POST.get('kind', 'colab')
    if kind == 'colab':
        log = get_object_or_404(ColaboradorLog, pk=pk)
    else:
        log = get_object_or_404(InvestorLog, pk=pk)
    col_pk = log.colaboracion_id
    log.delete()
    return redirect('crm:colaboracion_detail', pk=col_pk)


@login_required
def colaboracion_log_upd(request, pk):
    """Edita type+date+summary de un ColaboradorLog o InvestorLog y redirige a la colaboración."""
    from crm.models import ColaboradorLog
    if not can_edit(request.user) or request.method != 'POST':
        return HttpResponseForbidden()
    kind = request.POST.get('kind', 'colab')
    if kind == 'colab':
        log = get_object_or_404(ColaboradorLog, pk=pk)
    else:
        log = get_object_or_404(InvestorLog, pk=pk)
    log.date    = request.POST.get('date') or None
    log.type    = request.POST.get('type', log.type)
    log.summary = request.POST.get('summary', '').strip()
    log.save(update_fields=['date', 'type', 'summary'])
    return redirect('crm:colaboracion_detail', pk=log.colaboracion_id)


@login_required
def colaboracion_edit_inline(request, pk):
    from crm.models import ColaboradorLog, EstadoColaboracion
    from datetime import date as _date
    col = get_object_or_404(
        Colaboracion.objects.select_related('company', 'status', 'colaborador', 'investor'), pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        status_anterior_nombre = col.status.nombre if col.status else '—'
        status_anterior_id     = col.status_id

        status_raw      = request.POST.get('status', '').strip()
        col.status_id   = int(status_raw) if status_raw.isdigit() else None
        col.tipo_relacion = request.POST.get('tipo_relacion', '').strip()
        col.date        = request.POST.get('date', '').strip() or None
        col.intro_by    = request.POST.get('intro_by', '').strip()
        col.next_action = request.POST.get('next_action', '').strip()
        col.next_date   = request.POST.get('next_date', '').strip() or None
        col.descripcion = request.POST.get('descripcion', '').strip()
        col.save(update_fields=['status_id', 'tipo_relacion', 'date', 'intro_by',
                                'next_action', 'next_date', 'descripcion'])

        # Registrar cambio de estado en cronología si el estado cambió
        if col.status_id != status_anterior_id:
            nuevo = EstadoColaboracion.objects.filter(pk=col.status_id).first()
            nuevo_nombre = nuevo.nombre if nuevo else '—'
            autor = request.user.get_full_name() or request.user.username
            nota  = f'Estado actualizado: {status_anterior_nombre} → {nuevo_nombre} ({col.company.name})'
            if col.colaborador_id:
                ColaboradorLog.objects.create(
                    colaborador_id=col.colaborador_id,
                    date=_date.today(), type='Estado',
                    summary=nota, created_by=autor,
                    context='colaboracion', colaboracion=col,
                )
            elif col.investor_id:
                InvestorLog.objects.create(
                    investor_id=col.investor_id,
                    date=_date.today(), type='Estado',
                    summary=nota, created_by=autor,
                    context='colaboracion', colaboracion=col,
                )

        messages.success(request, 'Colaboración actualizada.')
    return redirect('crm:colaboracion_detail', pk=pk)


@login_required
def colaboracion_chrono(request, pk):
    from crm.models import ColaboradorLog, InteraccionColaboracion
    col = get_object_or_404(Colaboracion.objects.select_related('company', 'colaborador', 'investor'), pk=pk)
    if not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()

    label = f'{col.contact.name if col.contact else "—"} · {col.company.name}'

    if request.method == 'POST':
        if not can_edit(request.user):
            return JsonResponse({'ok': False}, status=403)
        from datetime import date as _date
        log_type   = request.POST.get('type', 'Nota')
        summary    = request.POST.get('summary', '').strip()
        log_date   = request.POST.get('date') or None
        attachment_url = ''
        f = request.FILES.get('attachment')
        if f:
            if col.colaborador_id:
                saved = _save_contact_doc(f, 'Colaboradores', col.colaborador.name)
                slug  = _re.sub(r'[^\w\-.]', '_', col.colaborador.name.strip())
                attachment_url = reverse('crm:docs_contactos_download',
                                         args=('colaboradores', slug, pathlib.Path(saved).name))
            elif col.investor_id:
                saved = _save_contact_doc(f, 'Inversores', col.investor.name)
                slug  = _re.sub(r'[^\w\-.]', '_', col.investor.name.strip())
                attachment_url = reverse('crm:docs_contactos_download',
                                         args=('inversores', slug, pathlib.Path(saved).name))
        if col.colaborador_id:
            ColaboradorLog.objects.create(
                colaborador_id=col.colaborador_id,
                type=log_type, date=log_date or _date.today(),
                summary=summary,
                created_by=request.user.get_full_name() or request.user.username,
                context='colaboracion', colaboracion_id=col.pk,
                attachment_url=attachment_url,
            )
        elif col.investor_id:
            InvestorLog.objects.create(
                investor_id=col.investor_id,
                type=log_type, date=log_date or _date.today(),
                summary=summary,
                created_by=request.user.get_full_name() or request.user.username,
                context='colaboracion', colaboracion_id=col.pk,
                attachment_url=attachment_url,
            )
        # También guarda en InteraccionColaboracion para compatibilidad con la página
        InteraccionColaboracion.objects.create(
            colaboracion=col, type=log_type,
            date=log_date or _date.today(), note=summary,
        )
        return JsonResponse({'ok': True})

    # GET: combinar ColaboradorLog/InvestorLog + InteraccionColaboracion
    from datetime import date as _date
    logs = []
    if col.colaborador_id:
        for l in ColaboradorLog.objects.filter(colaborador_id=col.colaborador_id, colaboracion_id=col.pk).order_by('-date', '-pk'):
            logs.append({'date': l.date, 'type': l.type, 'summary': l.summary or ''})
    elif col.investor_id:
        for l in InvestorLog.objects.filter(investor_id=col.investor_id, colaboracion_id=col.pk).order_by('-date', '-pk'):
            logs.append({'date': l.date, 'type': l.type, 'summary': l.summary or ''})
    # Añadir entradas antiguas de InteraccionColaboracion que no estén duplicadas
    existing_summaries = {(l['date'], l['summary']) for l in logs}
    for ic in InteraccionColaboracion.objects.filter(colaboracion=col).order_by('-date', '-pk'):
        key = (ic.date, ic.note)
        if key not in existing_summaries:
            logs.append({'date': ic.date, 'type': ic.type, 'summary': ic.note or ''})
    logs.sort(key=lambda l: (l['date'] or _date.min), reverse=True)
    data = [{'date': (l['date'].strftime('%d %b %Y') if l['date'] else '—'),
             'type': l['type'], 'summary': l['summary']} for l in logs]
    return JsonResponse({'logs': data, 'label': label})


@login_required
def investor_create(request):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            obj = Investor.objects.create(
                name=name,
                country=request.POST.get('country', '').strip(),
                type=request.POST.get('type', '').strip(),
                sectors=', '.join(request.POST.getlist('sectors')),
            )
            relation_id = request.POST.get('relation')
            if relation_id:
                obj.relation_id = relation_id
                obj.save()
            # Contacto persona pre-rellenado desde email (campos opcionales)
            contact_name = request.POST.get('contact_name', '').strip()
            if contact_name:
                InvestorContact.objects.create(
                    investor=obj,
                    name=contact_name,
                    role=request.POST.get('contact_role', '').strip(),
                    email=request.POST.get('contact_email', '').strip(),
                    phone=request.POST.get('contact_phone', '').strip(),
                )
            messages.success(request, f'Inversor «{obj.name}» creado.')
            return redirect('crm:investor_detail', pk=obj.pk)
    return redirect('crm:investors')


@login_required
def colaborador_create(request):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            obj = Colaborador.objects.create(
                name=name,
                country=request.POST.get('country', '').strip(),
                sectors=request.POST.get('sectors', '').strip(),
                notes=request.POST.get('notes', '').strip(),
                es_comprador=bool(request.POST.get('es_comprador')),
                es_colaborador=bool(request.POST.get('es_colaborador')),
                es_cliente=bool(request.POST.get('es_cliente')),
                es_proveedor=bool(request.POST.get('es_proveedor')),
            )
            # Contacto persona pre-rellenado desde email (campos opcionales)
            contact_name = request.POST.get('contact_name', '').strip()
            if contact_name:
                ColaboradorContacto.objects.create(
                    colaborador=obj,
                    name=contact_name,
                    role=request.POST.get('contact_role', '').strip(),
                    email=request.POST.get('contact_email', '').strip(),
                    phone=request.POST.get('contact_phone', '').strip(),
                )
            messages.success(request, f'Contacto «{obj.name}» creado.')
            return redirect('crm:colaborador_detail', pk=obj.pk)
    return redirect('crm:colaboradores')


@login_required
def colaborador_edit(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    obj = get_object_or_404(Colaborador, pk=pk)
    if request.method == 'POST':
        obj.name = request.POST.get('name', obj.name).strip()
        obj.country = request.POST.get('country', '').strip()
        obj.sectors = ', '.join(request.POST.getlist('sectors'))
        obj.notes = request.POST.get('notes', '').strip()
        obj.es_comprador = bool(request.POST.get('es_comprador'))
        obj.es_colaborador = bool(request.POST.get('es_colaborador'))
        obj.es_cliente = bool(request.POST.get('es_cliente'))
        obj.es_proveedor = bool(request.POST.get('es_proveedor'))
        obj.es_inversor_esporadico = bool(request.POST.get('es_inversor_esporadico'))
        relation_id = request.POST.get('relation')
        obj.relation_id = relation_id or None
        obj.save()
        # Guardar contactos
        names  = request.POST.getlist('contact_name')
        roles  = request.POST.getlist('contact_role')
        emails = request.POST.getlist('contact_email')
        phones = request.POST.getlist('contact_phone')
        from crm.models import ColaboradorContacto
        if request.user.role == 'admin':
            # Solo el admin puede eliminar contactos existentes
            obj.contacts.all().delete()
            for name, role, email, phone in zip(names, roles, emails, phones):
                if name.strip():
                    ColaboradorContacto.objects.create(
                        colaborador=obj,
                        name=name.strip(), role=role.strip(),
                        email=email.strip(), phone=phone.strip(),
                    )
        else:
            # El resto solo puede añadir contactos nuevos (sin borrar los existentes)
            ids_in_form = [v for v in request.POST.getlist('contact_id') if v]
            for name, role, email, phone in zip(names, roles, emails, phones):
                if name.strip() and name.strip() not in [
                    c.name for c in obj.contacts.filter(pk__in=ids_in_form)
                ]:
                    ColaboradorContacto.objects.get_or_create(
                        colaborador=obj, name=name.strip(),
                        defaults={'role': role.strip(), 'email': email.strip(), 'phone': phone.strip()},
                    )
        messages.success(request, 'Contacto actualizado.')
        return redirect('crm:colaborador_detail', pk=pk)
    return redirect('crm:colaborador_detail', pk=pk)


TIPO_CONTACTO_OPTS = [
    ('comprador',           'es_comprador',           'Comprador'),
    ('colaborador',         'es_colaborador',         'Colaborador'),
    ('cliente',             'es_cliente',             'Cliente'),
    ('proveedor',           'es_proveedor',           'Proveedor'),
    ('inversor_esporadico', 'es_inversor_esporadico', 'Inversor esporádico'),
]


@login_required
def colaboradores(request):
    qs = Colaborador.objects.select_related('relation').all()
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    view = request.GET.get('view', 'list')
    if q:
        qs = qs.filter(name__icontains=q)
    tipo_field = next((f for slug, f, _ in TIPO_CONTACTO_OPTS if slug == tipo), None)
    if tipo_field:
        qs = qs.filter(**{tipo_field: True})
    group = request.GET.get('group', '')
    cards = [
        {
            'colaborador': c,
            'activos_colab': c.colaboraciones.exclude(status__nombre__in=COLLAB_TERMINAL).count(),
            'activos_ma': c.contactos_ma.exclude(status__nombre__in=MA_TERMINAL).count() if c.es_comprador else 0,
        }
        for c in qs
    ]
    groups = None
    if group in ('country',):
        groups = {}
        for card in cards:
            key = getattr(card['colaborador'], group) or '—'
            groups.setdefault(key, []).append(card)

    etapas = list(EtapaRelacionColaborador.objects.all())
    pipe_stages = []
    for etapa in etapas:
        items = [c for c in cards if c['colaborador'].relation_id == etapa.pk]
        pipe_stages.append({'etapa': etapa, 'items': items})
    sin_etapa = [c for c in cards if c['colaborador'].relation_id is None]
    if sin_etapa:
        pipe_stages.insert(0, {'etapa': None, 'items': sin_etapa})

    return render(request, 'crm/colaboradores.html', {
        'active_nav': 'colaboradores', 'cards': cards, 'groups': groups,
        'group': group, 'q': q, 'tipo': tipo,
        'tipo_opts': TIPO_CONTACTO_OPTS,
        'view': view, 'pipe_stages': pipe_stages,
        'can_edit': can_edit(request.user),
    })


@login_required
def colaborador_set_relation(request, pk):
    if request.method == 'POST' and can_edit(request.user):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        relation_id = request.POST.get('relation_id') or None
        colaborador.relation_id = relation_id
        colaborador.save(update_fields=['relation_id'])
    return redirect(request.POST.get('next', 'crm:colaboradores'))


@login_required
def colaborador_detail(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)

    intros = list(colaborador.introductions.select_related('company', 'round', 'round__status', 'status').all())
    if request.user.role != 'admin':
        intros = [i for i in intros if can_see_company(request.user, i.company_id)]

    contactos_ma = list(colaborador.contactos_ma.select_related('proceso__company', 'status').all())
    if request.user.role != 'admin':
        contactos_ma = [c for c in contactos_ma if can_see_company(request.user, c.proceso.company_id)]

    colabs = colaborador.colaboraciones.select_related('company', 'status').all()
    if request.user.role != 'admin':
        colabs = colabs.filter(company_id__in=allowed_company_ids(request.user))
    colabs = list(colabs)

    # KPIs rondas
    INTRO_TERMINAL = ('Descartado', 'No contactado')
    intros_activas = [i for i in intros if i.status and i.status.nombre not in INTRO_TERMINAL]
    intros_invertidas = [i for i in intros if i.status and i.status.nombre == 'Invertido']
    intros_descartadas = [i for i in intros if i.status and i.status.nombre == 'Descartado']

    # KPIs M&A
    ma_activos = [c for c in contactos_ma if not c.status or c.status.nombre not in MA_TERMINAL]
    ma_vendidos = [c for c in contactos_ma if c.status and c.status.nombre == 'Vendido']
    ma_descartados = [c for c in contactos_ma if c.status and c.status.nombre == 'Descartado']
    ma_mejor_oferta = max((c.oferta_precio or 0 for c in contactos_ma), default=0)

    # KPIs Colaboraciones
    colab_activas = [c for c in colabs if not c.status or c.status.nombre not in COLLAB_TERMINAL]
    colab_firmadas = [c for c in colabs if c.status and c.status.nombre == 'Activo']
    colab_descartadas = [c for c in colabs if c.status and c.status.nombre == 'Descartado']

    chrono = list(colaborador.logs.select_related('round__company', 'proceso_ma__company', 'colaboracion__company').all())

    if request.method == 'POST' and can_edit(request.user):
        return redirect('crm:colaborador_detail', pk=pk)

    from crm.models import ProcesoMA, Colaboracion as ColaboracionModel
    log_rounds = Round.objects.filter(introductions__colaborador=colaborador).select_related('company').distinct()
    log_ma     = ProcesoMA.objects.filter(contactos__comprador=colaborador).select_related('company').distinct()
    log_colabs = ColaboracionModel.objects.filter(colaborador=colaborador).select_related('company').distinct()

    colaborador_companies = Company.objects.filter(
        colaboraciones__colaborador=colaborador
    ).distinct()
    return render(request, 'crm/colaborador_detail.html', {
        'active_nav': 'colaboradores', 'colaborador': colaborador,
        'is_admin': request.user.role == 'admin',
        'colaborador_companies': colaborador_companies,
        'intros': intros, 'contactos_ma': contactos_ma, 'colabs': colabs,
        'intros_activas': intros_activas, 'intros_invertidas': intros_invertidas,
        'intros_descartadas': intros_descartadas,
        'ma_activos': ma_activos, 'ma_vendidos': ma_vendidos,
        'ma_descartados': ma_descartados, 'ma_mejor_oferta': ma_mejor_oferta,
        'colab_activas': colab_activas, 'colab_firmadas': colab_firmadas,
        'colab_descartadas': colab_descartadas,
        'chrono': chrono,
        'log_rounds': log_rounds, 'log_ma': log_ma, 'log_colabs': log_colabs,
        'tipo_opts': TIPO_CONTACTO_OPTS,
        'etapas_relacion': EtapaRelacionColaborador.objects.all(),
        'sector_opts': SECTOR_OPTS,
        'can_edit': can_edit(request.user),
    })


@login_required
def settings_view(request):
    if request.method == 'POST':
        section = request.POST.get('section')
        if section == 'profile':
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.email = request.POST.get('email', '')
            request.user.mfa_enabled = bool(request.POST.get('mfa_enabled'))
            request.user.save()
            messages.success(request, 'Perfil actualizado.')
        elif section == 'catalogo' and request.user.role == Role.ADMIN:
            model = {
                'estado': EstadoPresentacion, 'fase': FaseRonda, 'relacion': EtapaRelacion,
                'estado_ma': EstadoMA, 'fase_ma': FaseMA, 'estado_colab': EstadoColaboracion,
                'relacion_colab': EtapaRelacionColaborador,
            }.get(request.POST.get('tipo'))
            if model:
                nombre = request.POST.get('nombre', '').strip()
                if request.POST.get('delete_id'):
                    model.objects.filter(pk=request.POST['delete_id']).delete()
                elif nombre:
                    model.objects.create(nombre=nombre, orden=model.objects.count())
            messages.success(request, 'Catálogo actualizado.')
        return redirect('crm:settings')

    return render(request, 'crm/settings.html', {
        'active_nav': 'settings',
        'estados': EstadoPresentacion.objects.all(),
        'fases': FaseRonda.objects.all(),
        'relaciones': EtapaRelacion.objects.all(),
        'estados_ma': EstadoMA.objects.all(),
        'fases_ma': FaseMA.objects.all(),
        'estados_colab': EstadoColaboracion.objects.all(),
        'relaciones_colab': EtapaRelacionColaborador.objects.all(),
        'is_admin': request.user.role == Role.ADMIN,
    })


# ─── Documentación ────────────────────────────────────────────────────────────

@login_required
def docs_centro(request):
    # ── Pestaña Participadas ─────────────────────────────────────────────────
    companies = visible_companies(request.user).prefetch_related('rounds', 'procesos_ma')
    participadas_data = []
    for c in companies:
        participadas_data.append({'company': c, 'total': c.documentos.count()})

    # ── Pestañas Inversores / Colaboradores ──────────────────────────────────
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    inversores_data = []
    colaboradores_data = []
    for tipo, bucket in (('Inversores', inversores_data), ('Colaboradores', colaboradores_data)):
        tipo_dir = root / tipo
        if tipo_dir.exists():
            for carpeta in sorted(tipo_dir.iterdir()):
                if carpeta.is_dir():
                    archivos = [f for f in carpeta.iterdir() if f.is_file()]
                    bucket.append({
                        'nombre': carpeta.name.replace('_', ' '),
                        'slug':   carpeta.name,
                        'count':  len(archivos),
                        'url':    reverse('crm:docs_contactos_carpeta',
                                         args=(tipo.lower(), carpeta.name)),
                    })

    tab = request.GET.get('tab', 'participadas')
    return render(request, 'crm/docs_centro.html', {
        'active_nav':        'docs_centro',
        'participadas_data': participadas_data,
        'inversores_data':   inversores_data,
        'colaboradores_data': colaboradores_data,
        'active_tab':        tab,
    })


@login_required
def docs_company(request, company_pk):
    companies = visible_companies(request.user)
    company = get_object_or_404(Company, pk=company_pk)
    if company not in companies:
        return HttpResponseForbidden()

    rounds = company.rounds.all()
    procesos = company.procesos_ma.all()
    base_qs = company.documentos.filter(round=None, proceso_ma=None)
    general_count = base_qs.filter(carpeta='general').count()

    carpetas = [
        {'label': 'General', 'icon': 'bi-folder2', 'count': general_count,
         'url': reverse('crm:docs_carpeta', args=(company_pk, 'general', 0))},
    ]
    for r in rounds:
        carpetas.append({'label': r.type, 'icon': 'bi-graph-up-arrow',
                         'count': r.documentos.count(),
                         'url': reverse('crm:docs_carpeta', args=(company_pk, 'ronda', r.pk))})
    for p in procesos:
        carpetas.append({'label': p.nombre, 'icon': 'bi-briefcase',
                         'count': p.documentos.count(),
                         'url': reverse('crm:docs_carpeta', args=(company_pk, 'ma', p.pk))})

    return render(request, 'crm/docs_company.html', {
        'active_nav': 'docs_centro',
        'company': company,
        'carpetas': carpetas,
    })


@login_required
def docs_carpeta(request, company_pk, tipo, ref_pk):
    companies = visible_companies(request.user)
    company = get_object_or_404(Company, pk=company_pk)
    if company not in companies:
        return HttpResponseForbidden()

    round_obj = proceso_obj = None
    if tipo == 'ronda':
        round_obj = get_object_or_404(Round, pk=ref_pk, company=company)
        docs = Documento.objects.filter(company=company, round=round_obj)
        carpeta_label = round_obj.type
    elif tipo == 'ma':
        proceso_obj = get_object_or_404(ProcesoMA, pk=ref_pk, company=company)
        docs = Documento.objects.filter(company=company, proceso_ma=proceso_obj)
        carpeta_label = proceso_obj.nombre
    elif tipo in ('emails', 'reuniones', 'notas'):
        docs = Documento.objects.filter(company=company, round=None, proceso_ma=None, carpeta=tipo)
        carpeta_label = tipo.capitalize()
    else:
        docs = Documento.objects.filter(company=company, round=None, proceso_ma=None, carpeta='general')
        carpeta_label = 'General'

    if request.method == 'POST':
        f = request.FILES.get('file')
        if f:
            doc = Documento(
                company=company,
                round=round_obj,
                proceso_ma=proceso_obj,
                carpeta=tipo if tipo in ('emails', 'reuniones', 'notas') else 'general',
                file=f,
                name=request.POST.get('name', '').strip() or f.name,
                description=request.POST.get('description', '').strip(),
                uploaded_by=request.user,
            )
            doc.save()
        return redirect(request.path)

    return render(request, 'crm/docs_carpeta.html', {
        'active_nav': 'docs_centro',
        'company': company,
        'carpeta_label': carpeta_label,
        'tipo': tipo,
        'ref_pk': ref_pk,
        'docs': docs,
        'round_obj': round_obj,
        'proceso_obj': proceso_obj,
    })


@login_required
def docs_delete(request, doc_pk):
    doc = get_object_or_404(Documento, pk=doc_pk)
    company = doc.company
    companies = visible_companies(request.user)
    if company not in companies:
        return HttpResponseForbidden()
    if not can_edit(request.user):
        return HttpResponseForbidden()
    tipo = 'ronda' if doc.round_id else ('ma' if doc.proceso_ma_id else 'general')
    ref_pk = doc.round_id or doc.proceso_ma_id or 0
    if request.method == 'POST':
        if doc.file:
            import os
            try:
                os.remove(doc.file.path)
            except FileNotFoundError:
                pass
        doc.delete()
    return redirect('crm:docs_carpeta', company_pk=company.pk, tipo=tipo, ref_pk=ref_pk)


# ─── Parse email .msg ─────────────────────────────────────────────────────────

@login_required
def parse_email(request):
    """Extrae metadatos del .msg y elimina el archivo inmediatamente (RGPD).
    El cuerpo se devuelve al browser solo para que el usuario pueda
    solicitar el resumen IA de forma explícita; el servidor no lo almacena."""
    import os, tempfile
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    f = request.FILES.get('file')
    if not f or not f.name.lower().endswith('.msg'):
        return JsonResponse({'error': 'Se esperaba un archivo .msg'}, status=400)

    with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as tmp:
        for chunk in f.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        import extract_msg
        msg      = extract_msg.Message(tmp_path)
        raw_date = msg.date
        sender   = str(msg.sender   or '').strip()
        to_field = str(msg.to       or '').strip()
        subject  = str(msg.subject  or '').strip()
        body     = str(msg.body     or '').strip()
        msg.close()
    except Exception as exc:
        return JsonResponse({'error': f'Error al leer el archivo: {exc}'}, status=400)
    finally:
        # Eliminación inmediata — cumplimiento RGPD
        os.unlink(tmp_path)

    user_email = (request.user.email or '').lower()
    if user_email and user_email in sender.lower():
        direction = 'Saliente (Out)'
    else:
        direction = 'Entrante (In)'

    # Parsear fecha — extract_msg puede devolver datetime o string
    date_str = ''
    if raw_date:
        import datetime as dt_mod
        if isinstance(raw_date, (dt_mod.datetime, dt_mod.date)):
            date_str = raw_date.strftime('%Y-%m-%d')
        else:
            # Intentar parsear como string RFC 2822 (formato email estándar)
            try:
                import email.utils
                parsed = email.utils.parsedate_to_datetime(str(raw_date))
                date_str = parsed.strftime('%Y-%m-%d')
            except Exception:
                try:
                    # Último recurso: extraer YYYY-MM-DD o DD/MM/YYYY
                    import re
                    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(raw_date))
                    if m:
                        date_str = m.group(0)
                except Exception:
                    pass

    # El texto inicial lo construye el JS a partir de los campos individuales
    summary_text = ''

    return JsonResponse({
        'date':         date_str,
        'type':         'Email',
        'direction':    direction,
        'sender':       sender,
        'to_field':     to_field,
        'subject':      subject,
    })


@login_required
def parse_contact_email(request):
    """Extrae datos de contacto de un .msg para pre-rellenar el formulario de nuevo contacto.
    Sin IA ni llamadas externas. El archivo se elimina inmediatamente (RGPD)."""
    import os, re, tempfile
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    f = request.FILES.get('file')
    if not f or not f.name.lower().endswith('.msg'):
        return JsonResponse({'error': 'Se esperaba un archivo .msg'}, status=400)

    with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as tmp:
        for chunk in f.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        import extract_msg
        msg    = extract_msg.Message(tmp_path)
        sender = str(msg.sender or '').strip()
        body   = str(msg.body   or '').strip()
        msg.close()
    except Exception as exc:
        return JsonResponse({'error': f'Error al leer el archivo: {exc}'}, status=400)
    finally:
        os.unlink(tmp_path)  # eliminación inmediata — RGPD

    # ── Extraer email del remitente ────────────────────────────────────────
    email_match = re.search(r'<([^>@\s]+@[^>]+)>', sender)
    contact_email = email_match.group(1).strip() if email_match else (
        sender if '@' in sender else ''
    )

    # ── Extraer nombre de la persona (antes de | o <) ─────────────────────
    contact_name = re.split(r'\s*[|<]', sender)[0].strip()

    # ── Extraer nombre de empresa: primero del display name, luego del dominio
    company_name = ''
    pipe_match = re.search(r'\|\s*([^<|]+?)(?:\s*<|$)', sender)
    if pipe_match:
        company_name = pipe_match.group(1).strip()
    elif contact_email and '@' in contact_email:
        domain = contact_email.split('@')[-1]
        # Quitar TLD y capitalizar (ej. "kfund.co" → "Kfund")
        company_name = domain.split('.')[0].capitalize()

    # ── Extraer teléfono del cuerpo (regex, sin IA) ───────────────────────
    contact_phone = ''
    if body:
        phone_candidates = re.findall(
            r'(?<!\d)(\+?[\d][\d\s\.\-\(\)]{7,16}[\d])(?!\d)', body
        )
        for candidate in phone_candidates:
            digits = re.sub(r'\D', '', candidate)
            if 9 <= len(digits) <= 15 and not re.match(r'^(19|20)\d{6}$', digits):
                contact_phone = candidate.strip()
                break

    # ── Extraer cargo desde la firma del email (heurística, sin IA) ───────
    contact_role = ''
    if body:
        ROLE_RE = re.compile(
            r'\b(director[a]?|gerente|presidente|ceo|cfo|cto|coo|cso|cpo|'
            r'vice[- ]?president[ae]?|vp\b|socio|partner|managing partner|'
            r'analista|analyst|manager|responsable|jefe|head of|chief|'
            r'founder|co-?founder|fundador|associate|inversor|investor|'
            r'advisor|asesor|consultor|consultant|coordinador|coordinator|'
            r'principal|ejecutiv[ao]|senior|director general|'
            r'managing director|investment manager|portfolio manager)\b',
            re.IGNORECASE,
        )
        # Buscar en la zona de firma: últimas 30 líneas o tras separador '--'
        lines = body.split('\n')
        sig_start = 0
        for i, ln in enumerate(lines):
            if ln.strip() in ('--', '- -', '—', '___'):
                sig_start = i + 1
                break
        sig_lines = lines[max(sig_start, len(lines) - 30):]

        for ln in sig_lines:
            ln = ln.strip()
            if not ln or len(ln) > 90:
                continue
            # Saltar líneas que parezcan emails, URLs o teléfonos
            if re.search(r'[@://]|\d{6,}', ln):
                continue
            # Saltar si coincide con el nombre o empresa del contacto
            if contact_name and contact_name.split()[0].lower() in ln.lower():
                continue
            if company_name and company_name.split()[0].lower() in ln.lower():
                continue
            if ROLE_RE.search(ln):
                # Limpiar separadores iniciales
                clean = re.sub(r'^[\s\|\-·•–]+', '', ln).strip()
                if 2 < len(clean) <= 80:
                    contact_role = clean
                    break

    return JsonResponse({
        'contact_name':  contact_name,
        'contact_email': contact_email,
        'contact_phone': contact_phone,
        'contact_role':  contact_role,
        'company_name':  company_name,
    })


# ─── Doc-drop: adjuntar documento a la cronología ─────────────────────────────

def _save_contact_doc(f, entity_type, entity_name):
    """Guarda el fichero en CONTACT_DOCS_ROOT/<entity_type>/<entity_name>/ y devuelve la ruta."""
    slug = _re.sub(r'[^\w\-.]', '_', entity_name.strip())
    dest_dir = pathlib.Path(settings.CONTACT_DOCS_ROOT) / entity_type / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f.name
    # Si ya existe, añadir sufijo numérico
    counter = 1
    while dest_path.exists():
        stem, suffix = pathlib.Path(f.name).stem, pathlib.Path(f.name).suffix
        dest_path = dest_dir / f'{stem}_{counter}{suffix}'
        counter += 1
    with open(dest_path, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)
    return str(dest_path)


@login_required
def investor_doc_drop(request, pk):
    if not can_edit(request.user):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    investor = get_object_or_404(Investor, pk=pk)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No se recibió ningún archivo'}, status=400)

    from datetime import date as _date
    log_date  = request.POST.get('date') or str(_date.today())
    log_type  = request.POST.get('type', 'Nota')
    summary   = request.POST.get('summary', '').strip()

    slug = _re.sub(r'[^\w\-.]', '_', investor.name.strip())
    saved_path = _save_contact_doc(f, 'Inversores', investor.name)
    actual_filename = pathlib.Path(saved_path).name
    attachment_url = reverse('crm:docs_contactos_download',
                             args=('inversores', slug, actual_filename))

    if not summary:
        summary = actual_filename
    elif actual_filename not in summary:
        summary = f'{summary}\n[Adjunto: {actual_filename}]'

    ctx      = request.POST.get('context', '')
    round_id = request.POST.get('round_id') or None
    ma_id    = request.POST.get('proceso_ma_id') or None
    colab_id = request.POST.get('colaboracion_id') or None
    InvestorLog.objects.create(
        investor=investor,
        date=log_date or None,
        type=log_type,
        summary=summary,
        attachment_url=attachment_url,
        created_by=request.user.get_full_name() or request.user.username,
        context=ctx,
        round_id=round_id if ctx == 'ronda' else None,
        proceso_ma_id=ma_id if ctx == 'ma' else None,
        colaboracion_id=colab_id if ctx == 'colaboracion' else None,
    )
    return JsonResponse({'ok': True, 'path': saved_path})


@login_required
def colaborador_doc_drop(request, pk):
    if not can_edit(request.user):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    colaborador = get_object_or_404(Colaborador, pk=pk)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No se recibió ningún archivo'}, status=400)

    from datetime import date as _date
    from crm.models import ColaboradorLog
    log_date  = request.POST.get('date') or str(_date.today())
    log_type  = request.POST.get('type', 'Nota')
    summary   = request.POST.get('summary', '').strip()

    slug = _re.sub(r'[^\w\-.]', '_', colaborador.name.strip())
    saved_path = _save_contact_doc(f, 'Colaboradores', colaborador.name)
    actual_filename = pathlib.Path(saved_path).name
    attachment_url = reverse('crm:docs_contactos_download',
                             args=('colaboradores', slug, actual_filename))

    if not summary:
        summary = actual_filename
    elif actual_filename not in summary:
        summary = f'{summary}\n[Adjunto: {actual_filename}]'

    ctx      = request.POST.get('context', '')
    round_id = request.POST.get('round_id') or None
    ma_id    = request.POST.get('proceso_ma_id') or None
    colab_id = request.POST.get('colaboracion_id') or None
    ColaboradorLog.objects.create(
        colaborador=colaborador,
        date=log_date or None,
        type=log_type,
        summary=summary,
        attachment_url=attachment_url,
        created_by=request.user.get_full_name() or request.user.username,
        context=ctx,
        round_id=round_id if ctx == 'ronda' else None,
        proceso_ma_id=ma_id if ctx == 'ma' else None,
        colaboracion_id=colab_id if ctx == 'colaboracion' else None,
    )
    return JsonResponse({'ok': True, 'path': saved_path})


# ─── Repositorio de documentos de Inversores / Colaboradores ──────────────────

@login_required
def docs_contactos(request):
    """Lista las carpetas de inversores y colaboradores en CONTACT_DOCS_ROOT."""
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    entidades = []
    for tipo in ('Inversores', 'Colaboradores'):
        tipo_dir = root / tipo
        if tipo_dir.exists():
            for carpeta in sorted(tipo_dir.iterdir()):
                if carpeta.is_dir():
                    archivos = [f for f in carpeta.iterdir() if f.is_file()]
                    entidades.append({
                        'tipo':   tipo,
                        'nombre': carpeta.name.replace('_', ' '),
                        'slug':   carpeta.name,
                        'count':  len(archivos),
                        'url':    reverse('crm:docs_contactos_carpeta',
                                         args=(tipo.lower(), carpeta.name)),
                    })
    return render(request, 'crm/docs_contactos.html', {
        'active_nav': 'docs_contactos',
        'entidades':  entidades,
        'root':       str(root),
    })


@login_required
def docs_contactos_carpeta(request, tipo, slug):
    """Lista los archivos dentro de CONTACT_DOCS_ROOT/<tipo>/<slug>/."""
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    carpeta = root / tipo.capitalize() / slug
    if not carpeta.exists():
        raise Http404

    if request.method == 'POST' and can_edit(request.user):
        fname = request.POST.get('delete_file', '')
        target = carpeta / pathlib.Path(fname).name
        if target.exists() and target.parent == carpeta:
            target.unlink()
        return redirect(request.path)

    archivos = sorted(
        [f for f in carpeta.iterdir() if f.is_file()],
        key=lambda f: f.stat().st_mtime, reverse=True
    )

    # Buscar qué log referencia cada archivo para poder enlazar a la cronología
    from crm.models import InvestorLog, ColaboradorLog, Investor, Colaborador as ColaboradorModel
    es_inversor = tipo.lower() == 'inversores'
    LogModel = InvestorLog if es_inversor else ColaboradorLog
    fk_field  = 'investor_id' if es_inversor else 'colaborador_id'
    detail_name = 'crm:investor_detail' if es_inversor else 'crm:colaborador_detail'

    # Resolver el PK de la entidad para el link al detalle
    entity_pk = None
    entity_detail_url = None
    if es_inversor:
        inv = Investor.objects.filter(name__iexact=slug.replace('_', ' ')).first()
        if not inv:
            inv = Investor.objects.filter(name__regex=rf'^{slug.replace("_", ".?")}$').first()
        if inv:
            entity_pk = inv.pk
            entity_detail_url = reverse('crm:investor_detail', args=[inv.pk])
    else:
        col = ColaboradorModel.objects.filter(name__iexact=slug.replace('_', ' ')).first()
        if not col:
            col = ColaboradorModel.objects.filter(name__regex=rf'^{slug.replace("_", ".?")}$').first()
        if col:
            entity_pk = col.pk
            entity_detail_url = reverse('crm:colaborador_detail', args=[col.pk])

    # Carga todos los logs de este slug que tengan attachment_url
    logs_con_adjunto = {
        l.attachment_url.rsplit('/', 1)[-1]: l
        for l in LogModel.objects.filter(attachment_url__icontains=slug)
        if l.attachment_url
    }

    files_data = []
    for f in archivos:
        log = logs_con_adjunto.get(f.name)
        cronologia_url = None
        if log:
            epk = getattr(log, fk_field)
            cronologia_url = reverse(detail_name, args=[epk]) + f'#log-{log.pk}'
        files_data.append({
            'name':           f.name,
            'size_kb':        round(f.stat().st_size / 1024, 1),
            'url':            reverse('crm:docs_contactos_download', args=(tipo, slug, f.name)),
            'cronologia_url': cronologia_url,
        })

    return render(request, 'crm/docs_contactos_carpeta.html', {
        'active_nav':        'docs_centro',
        'tipo':              tipo.capitalize(),
        'nombre':            slug.replace('_', ' '),
        'files':             files_data,
        'can_edit':          can_edit(request.user),
        'entity_detail_url': entity_detail_url,
    })


@login_required
def docs_contactos_download(request, tipo, slug, filename):
    """Sirve un archivo del repositorio de contactos."""
    import mimetypes
    from django.http import FileResponse
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    safe_name = pathlib.Path(filename).name
    path = root / tipo.capitalize() / slug / safe_name
    if not path.exists() or not path.is_file():
        raise Http404
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(open(path, 'rb'), content_type=mime or 'application/octet-stream',
                        as_attachment=False, filename=safe_name)
