from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from crm.forms import ColaboracionForm, CompanyForm, ContactoMAForm, ProcesoMAForm, RoundForm, UserForm
from crm.models import (
    Colaboracion, ColaboradorContacto, Colaborador, Company, CompradorContacto, Comprador,
    ContactoMA, EstadoColaboracion, EstadoMA, EstadoPresentacion, EtapaRelacion,
    FaseRonda, InboxMessage, Interaction, InteraccionColaboracion, InteraccionMA,
    Introduction, Investor, InvestorLog, ProcesoMA, Round,
)
from crm.permissions import (
    allowed_company_ids, can_edit, can_see_company, visible_companies, visible_introductions, visible_investors,
)
from crm.utils import (
    MA_ESTADO_W, MA_TERMINAL, COLLAB_TERMINAL,
    active_rounds, company_invertido, proceso_ma_vendido, proceso_ma_weighted,
    round_invertido, round_weighted, summarize_email,
)


@login_required
def home(request):
    companies = visible_companies(request.user)
    open_rounds = Round.objects.filter(company__in=companies).exclude(status__nombre='Cerrada')
    closed_rounds = Round.objects.filter(company__in=companies, status__nombre='Cerrada')

    closed_kpis = {
        'count': closed_rounds.count(),
        'total': sum(round_invertido(r) for r in closed_rounds),
    }
    open_kpis = {
        'count': open_rounds.count(),
        'target': sum(r.target or 0 for r in open_rounds),
        'invertido': sum(round_invertido(r) for r in open_rounds),
        'weighted': sum(round_weighted(r) for r in open_rounds),
    }
    return render(request, 'crm/home.html', {
        'active_nav': 'home',
        'closed_kpis': closed_kpis,
        'open_kpis': open_kpis,
        'open_rounds': open_rounds.select_related('company'),
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
        cards.append({'company': c, 'target': target, 'invertido': inv, 'pct': min(pct, 100)})

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
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            messages.success(request, 'Participada creada.')
            return redirect('crm:company_detail', pk=company.pk)
    else:
        form = CompanyForm()
    return render(request, 'crm/company_form.html', {'active_nav': 'companies', 'form': form, 'title': 'Nueva participada'})


@login_required
def company_detail(request, pk):
    if not can_see_company(request.user, pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=pk)
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
    colaboraciones = company.colaboraciones.select_related('colaborador', 'status').all()

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
        'can_edit': can_edit(request.user),
    })


@login_required
def company_edit(request, pk):
    if not can_edit(request.user) or not can_see_company(request.user, pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Participada actualizada.')
            return redirect('crm:company_detail', pk=company.pk)
    else:
        form = CompanyForm(instance=company)
    return render(request, 'crm/company_form.html', {'active_nav': 'companies', 'form': form, 'title': f'Editar {company.name}'})


@login_required
def round_create(request, company_pk):
    if not can_edit(request.user) or not can_see_company(request.user, company_pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        form = RoundForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.company = company
            r.save()
            messages.success(request, 'Ronda creada.')
            return redirect('crm:round_detail', pk=r.pk)
    else:
        form = RoundForm()
    return render(request, 'crm/round_form.html', {'active_nav': 'companies', 'form': form, 'title': f'Nueva ronda — {company.name}'})


@login_required
def round_detail(request, pk):
    r = get_object_or_404(Round.objects.select_related('company', 'status'), pk=pk)
    if not can_see_company(request.user, r.company_id):
        return HttpResponseForbidden()

    intros = r.introductions.select_related('investor', 'status').all()
    q = request.GET.get('q', '').strip().lower()
    if q:
        intros = [i for i in intros if q in (i.investor.name + ' ' + i.investor.type + ' ' + (i.intro_by or '')).lower()]

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

    return render(request, 'crm/round_detail.html', {
        'active_nav': 'companies',
        'round': r, 'company': r.company,
        'kpis': kpis, 'tab': tab, 'q': request.GET.get('q', ''),
        'intros': intros,
        'pipe_stages': [stage_data(s) for s in pipe_stages],
        'end_stages': [stage_data(s) for s in end_stages],
        'can_edit': can_edit(request.user),
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
    intro.status = estado
    intro.save(update_fields=['status'])
    return redirect(reverse('crm:round_detail', kwargs={'pk': intro.round_id}) + '?tab=pipeline')


@login_required
def investors(request):
    qs = visible_investors(request.user)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q)
    group = request.GET.get('group', '')

    cards = []
    for v in qs.select_related('relation'):
        active = v.introductions.exclude(status__nombre__in=['Descartado', 'No contactado']).count()
        cards.append({'investor': v, 'active': active})

    groups = None
    if group in ('type', 'country'):
        groups = {}
        for card in cards:
            key = getattr(card['investor'], group) or '—'
            groups.setdefault(key, []).append(card)

    return render(request, 'crm/investors.html', {
        'active_nav': 'investors', 'cards': cards, 'groups': groups, 'group': group, 'q': q,
        'can_edit': can_edit(request.user),
    })


@login_required
def investor_detail(request, pk):
    investor = get_object_or_404(Investor, pk=pk)
    if request.user.role == 'ceo' and not visible_investors(request.user).filter(pk=pk).exists():
        return HttpResponseForbidden()

    intros = investor.introductions.select_related('company', 'round', 'status').all()
    if request.user.role != 'admin':
        intros = intros.filter(company_id__in=allowed_company_ids(request.user))

    chrono = []
    for log in investor.logs.select_related('round__company').all():
        if request.user.role == 'admin' or not log.round or can_see_company(request.user, log.round.company_id):
            chrono.append({'date': log.date, 'type': log.type, 'summary': log.summary,
                            'company': log.round.company if log.round else None, 'round': log.round, 'editable': True, 'id': log.id})
    for it in intros:
        for interaction in it.interactions.all():
            chrono.append({'date': interaction.date, 'type': interaction.type or 'Nota', 'summary': interaction.note,
                            'company': it.company, 'round': it.round, 'editable': False, 'id': None})
    chrono.sort(key=lambda x: x['date'] or '', reverse=True)
    last_contact = max((x['date'] for x in chrono if x['date']), default=None)

    return render(request, 'crm/investor_detail.html', {
        'active_nav': 'investors', 'investor': investor, 'intros': intros, 'chrono': chrono,
        'last_contact': last_contact, 'can_edit': can_edit(request.user),
    })


@login_required
def investor_log_create(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    investor = get_object_or_404(Investor, pk=pk)
    if request.method == 'POST':
        from crm.models import InvestorLog
        InvestorLog.objects.create(
            investor=investor, type=request.POST.get('type', 'Nota'),
            date=request.POST.get('date') or None, summary=request.POST.get('summary', ''),
        )
        messages.success(request, 'Contacto registrado.')
    return redirect('crm:investor_detail', pk=investor.pk)


@login_required
def presentaciones(request):
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

    return render(request, 'crm/presentaciones.html', {
        'active_nav': 'presentaciones', 'intros': intros, 'q': q, 'estado_id': estado_id,
        'estados': EstadoPresentacion.objects.all(),
    })


@login_required
def inbox(request):
    if request.method == 'POST':
        if not can_edit(request.user):
            return HttpResponseForbidden()
        msg = get_object_or_404(InboxMessage, pk=request.POST.get('message_id'))
        summary = request.POST.get('summary', '').strip()
        investor_id = request.POST.get('investor_id') or None
        round_id = request.POST.get('round_id') or None

        if summary and investor_id:
            investor = get_object_or_404(Investor, pk=investor_id)
            if round_id:
                round_obj = get_object_or_404(Round, pk=round_id)
                intro, _created = Introduction.objects.get_or_create(
                    investor=investor, round=round_obj,
                    defaults={'company': round_obj.company, 'intro_by': 'Email',
                              'status': EstadoPresentacion.objects.order_by('orden', 'id').first()},
                )
                Interaction.objects.create(introduction=intro, date=msg.date, type='Email', note=summary)
            else:
                InvestorLog.objects.create(investor=investor, date=msg.date, type='Email', summary=summary)
            msg.investor = investor
            msg.round_id = round_id
        msg.unread = False
        msg.saved = True
        msg.save()
        messages.success(request, 'Email guardado en la cronología.')
        return redirect('crm:inbox')

    msgs = InboxMessage.objects.select_related('investor', 'round').all()
    sel_id = request.GET.get('id')
    selected = None
    if sel_id:
        selected = get_object_or_404(InboxMessage, pk=sel_id)
    elif msgs:
        selected = msgs.first()

    suggested_investor = None
    summary = ''
    open_rounds = []
    if selected:
        if selected.unread and not selected.saved:
            selected.unread = False
            selected.save(update_fields=['unread'])
        summary = summarize_email(selected.subject, selected.body)
        if selected.from_email:
            domain = selected.from_email.split('@')[-1].lower()
            for inv in Investor.objects.all():
                if any(c.email and c.email.split('@')[-1].lower() == domain for c in inv.contacts.all()):
                    suggested_investor = inv
                    break
        for company in visible_companies(request.user):
            for r in active_rounds(company):
                open_rounds.append(r)

    return render(request, 'crm/inbox.html', {
        'active_nav': 'inbox', 'msgs': msgs, 'selected': selected, 'summary': summary,
        'suggested_investor': suggested_investor, 'investors': Investor.objects.all(),
        'open_rounds': open_rounds, 'can_edit': can_edit(request.user),
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


# ─── M&A ─────────────────────────────────────────────────────────────────────

@login_required
def proceso_ma_create(request, company_pk):
    if not can_edit(request.user) or not can_see_company(request.user, company_pk):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        form = ProcesoMAForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.company = company
            p.save()
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
    contactos = proceso.contactos.select_related('comprador', 'status').all()

    q = request.GET.get('q', '').strip().lower()
    if q:
        contactos = [c for c in contactos if q in c.comprador.name.lower()]

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
        form = ContactoMAForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.proceso = proceso
            c.save()
            messages.success(request, 'Comprador añadido.')
            return redirect('crm:proceso_ma_detail', pk=pk)
    else:
        form = ContactoMAForm()

    return render(request, 'crm/proceso_ma_detail.html', {
        'active_nav': 'companies',
        'proceso': proceso, 'company': proceso.company,
        'kpis': kpis, 'tab': tab, 'q': request.GET.get('q', ''),
        'contactos': contactos,
        'pipe_stages': [stage_data(s) for s in pipe_stages],
        'end_stages': [stage_data(s) for s in end_stages],
        'form': form,
        'can_edit': can_edit(request.user),
    })


@login_required
def contacto_ma_set_status(request, pk):
    if request.method != 'POST' or not can_edit(request.user):
        return HttpResponseForbidden()
    contacto = get_object_or_404(ContactoMA, pk=pk)
    if not can_see_company(request.user, contacto.proceso.company_id):
        return HttpResponseForbidden()
    estado = get_object_or_404(EstadoMA, pk=request.POST.get('estado_id'))
    contacto.status = estado
    contacto.save(update_fields=['status'])
    return redirect(reverse('crm:proceso_ma_detail', kwargs={'pk': contacto.proceso_id}) + '?tab=pipeline')


@login_required
def compradores(request):
    qs = Comprador.objects.select_related('relation').all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q)
    group = request.GET.get('group', '')
    cards = [{'comprador': c, 'activos': c.contactos_ma.exclude(status__nombre__in=MA_TERMINAL).count()} for c in qs]
    groups = None
    if group in ('type', 'country'):
        groups = {}
        for card in cards:
            key = getattr(card['comprador'], group) or '—'
            groups.setdefault(key, []).append(card)
    return render(request, 'crm/compradores.html', {
        'active_nav': 'compradores', 'cards': cards, 'groups': groups, 'group': group, 'q': q,
        'can_edit': can_edit(request.user),
    })


@login_required
def comprador_detail(request, pk):
    comprador = get_object_or_404(Comprador, pk=pk)
    contactos_ma = comprador.contactos_ma.select_related('proceso__company', 'status').all()
    if request.user.role != 'admin':
        contactos_ma = contactos_ma.filter(proceso__company_id__in=allowed_company_ids(request.user))

    chrono = []
    for c in contactos_ma:
        for inter in c.interactions.all():
            chrono.append({'date': inter.date, 'type': inter.type or 'Nota', 'summary': inter.note,
                           'company': c.proceso.company, 'proceso': c.proceso})
    chrono.sort(key=lambda x: x['date'] or '', reverse=True)
    last_contact = max((x['date'] for x in chrono if x['date']), default=None)

    if request.method == 'POST' and can_edit(request.user):
        contacto_id = request.POST.get('contacto_id')
        if contacto_id:
            contacto = get_object_or_404(ContactoMA, pk=contacto_id)
            InteraccionMA.objects.create(
                contacto=contacto,
                type=request.POST.get('type', 'Nota'),
                date=request.POST.get('date') or None,
                note=request.POST.get('summary', ''),
            )
            messages.success(request, 'Interacción registrada.')
        return redirect('crm:comprador_detail', pk=pk)

    return render(request, 'crm/comprador_detail.html', {
        'active_nav': 'compradores', 'comprador': comprador,
        'contactos_ma': contactos_ma, 'chrono': chrono, 'last_contact': last_contact,
        'can_edit': can_edit(request.user),
    })


# ─── Colaboraciones ───────────────────────────────────────────────────────────

@login_required
def colaboraciones_global(request):
    from django.db.models import Q as DQ
    companies = visible_companies(request.user)
    qs = Colaboracion.objects.filter(company__in=companies).select_related('company', 'colaborador', 'status')
    q = request.GET.get('q', '').strip()
    estado_id = request.GET.get('estado', '')
    if q:
        qs = qs.filter(DQ(colaborador__name__icontains=q) | DQ(company__name__icontains=q) | DQ(descripcion__icontains=q))
    if estado_id:
        qs = qs.filter(status_id=estado_id)
    return render(request, 'crm/colaboraciones_global.html', {
        'active_nav': 'colaboraciones', 'colaboraciones': qs, 'q': q, 'estado_id': estado_id,
        'estados': EstadoColaboracion.objects.all(),
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

    if request.method == 'POST' and can_edit(request.user):
        InteraccionColaboracion.objects.create(
            colaboracion=col,
            type=request.POST.get('type', 'Nota'),
            date=request.POST.get('date') or None,
            note=request.POST.get('summary', ''),
        )
        messages.success(request, 'Interacción registrada.')
        return redirect('crm:colaboracion_detail', pk=pk)

    chrono = col.interactions.all()
    return render(request, 'crm/colaboracion_detail.html', {
        'active_nav': 'colaboraciones', 'col': col, 'chrono': chrono,
        'can_edit': can_edit(request.user),
    })


@login_required
def colaboradores(request):
    qs = Colaborador.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q)
    group = request.GET.get('group', '')
    cards = [{'colaborador': c, 'activos': c.colaboraciones.exclude(status__nombre__in=COLLAB_TERMINAL).count()} for c in qs]
    groups = None
    if group in ('type', 'country'):
        groups = {}
        for card in cards:
            key = getattr(card['colaborador'], group) or '—'
            groups.setdefault(key, []).append(card)
    return render(request, 'crm/colaboradores.html', {
        'active_nav': 'colaboradores', 'cards': cards, 'groups': groups, 'group': group, 'q': q,
        'can_edit': can_edit(request.user),
    })


@login_required
def colaborador_detail(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    colabs = colaborador.colaboraciones.select_related('company', 'status').all()
    if request.user.role != 'admin':
        colabs = colabs.filter(company_id__in=allowed_company_ids(request.user))
    return render(request, 'crm/colaborador_detail.html', {
        'active_nav': 'colaboradores', 'colaborador': colaborador, 'colabs': colabs,
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
                'estado_ma': EstadoMA, 'estado_colab': EstadoColaboracion,
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
        'estados_colab': EstadoColaboracion.objects.all(),
        'is_admin': request.user.role == Role.ADMIN,
    })
