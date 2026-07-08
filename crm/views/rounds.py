import re as _re
from crm.views.common import *
from crm.views.docs import _save_contact_doc


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
@login_required
def round_delete(request, pk):
    from accounts.models import Role
    r = get_object_or_404(Round.objects.select_related('company'), pk=pk)
    if request.user.role != Role.ADMIN or not can_see_company(request.user, r.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        company_pk = r.company_id
        r.delete()
        messages.success(request, 'Ronda de inversión eliminada.')
        return redirect('crm:company_detail', pk=company_pk)
    return HttpResponseForbidden()


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
    from accounts.models import Role
    return render(request, 'crm/round_form.html', {
        'active_nav': 'companies', 'form': form,
        'title': f'Editar ronda — {r.company.name}', 'round': r,
        'fase_logs': list(r.fase_logs.select_related('fase').order_by('date', 'pk')),
        'fases_ronda': list(FaseRonda.objects.order_by('pk')),
        'is_admin': request.user.role == Role.ADMIN,
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

    pipe_stages = [e for e in estados if e.nombre not in ('Invertido', 'Descartado')]
    end_stages = [e for e in estados if e.nombre in ('Invertido', 'Descartado')]

    def stage_data(stage):
        items = [i for i in intros if i.status_id == stage.id]
        return {'estado': stage, 'items': items, 'total': sum(i.ticket or 0 for i in items),
                'peso': int((ESTADO_W.get(stage.nombre, 0)) * 100)}

    all_investors = visible_investors(request.user).order_by('name')
    all_colaboradores = Colaborador.objects.order_by('name')
    all_rounds = Round.objects.filter(
        company_id__in=allowed_company_ids(request.user)
    ).select_related('company').order_by('company__name', 'type')

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
        'all_rounds': all_rounds,
        'fases_ronda': FaseRonda.objects.order_by('pk'),
        'fase_dates': dict(_fase_dates_r),
    })


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
        new_round_id = request.POST.get('round_id') or None
        if new_round_id:
            new_round = get_object_or_404(Round.objects.select_related('company'), pk=new_round_id)
            if can_see_company(request.user, new_round.company_id):
                intro.round_id = new_round_id
                intro.company_id = new_round.company_id
        intro.status_id  = request.POST.get('status') or intro.status_id
        intro.ticket     = request.POST.get('ticket') or None
        intro.date       = request.POST.get('date') or None
        intro.intro_by   = request.POST.get('intro_by', '')
        intro.next_action = request.POST.get('next_action', '')
        intro.next_date  = request.POST.get('next_date') or None
        intro.notes      = request.POST.get('notes', '')
        intro.save(update_fields=['round_id', 'company_id', 'status', 'ticket', 'date', 'intro_by', 'next_action', 'next_date', 'notes'])
        messages.success(request, 'Presentación actualizada.')
        return redirect(reverse('crm:round_detail', kwargs={'pk': intro.round_id}) + f'?tab={tab}')
    return HttpResponseForbidden()


@login_required
def intro_delete(request, pk):
    intro = get_object_or_404(Introduction, pk=pk)
    if not can_edit(request.user) or not can_see_company(request.user, intro.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        round_pk = intro.round_id
        tab = request.POST.get('tab', 'matriz')
        intro.delete()
        messages.success(request, 'Presentación eliminada.')
        return redirect(reverse('crm:round_detail', kwargs={'pk': round_pk}) + f'?tab={tab}')
    return HttpResponseForbidden()


def _set_intro_form_querysets(form, user):
    visible_ids = allowed_company_ids(user)
    form.fields['round'].queryset = (
        Round.objects.filter(company_id__in=visible_ids)
        .select_related('company')
        .order_by('company__name', 'type')
    )
    form.fields['investor'].queryset = visible_investors(user).order_by('name')


PRES_TERMINAL = ('Invertido', 'Descartado')

# Override PRES_GROUP_KEYS for the presentaciones views (uses investor/status keys instead of estado/round)
_PRES_GROUP_KEYS_TABLE = {
    'company':  lambda it: it.company.name,
    'investor': lambda it: it.investor.name,
    'round':    lambda it: it.round.type or '—',
    'status':   lambda it: it.status.nombre if it.status else '—',
}
_PRES_GROUP_LABELS_TABLE = [
    ('company', 'Participada'), ('investor', 'Inversor'),
    ('round', 'Ronda'), ('status', 'Estado'),
]


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

    g1, g2, g3 = parse_groups(request.GET, PRES_GROUP_KEYS)
    keyfns = [PRES_GROUP_KEYS[k] for k in (g1, g2, g3) if k]
    groups = build_groups(intros, keyfns) if keyfns else None

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

    g1, g2, g3 = parse_groups(request.GET, _PRES_GROUP_KEYS_TABLE.keys())
    active_groups = [g for g in (g1, g2, g3) if g]
    groups = build_groups(intros, [_PRES_GROUP_KEYS_TABLE[g] for g in active_groups]) if active_groups else None

    return render(request, 'crm/presentaciones.html', {
        'active_nav': 'presentaciones', 'intros': intros, 'groups': groups,
        'q': q, 'estado_id': estado_id,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': _PRES_GROUP_LABELS_TABLE,
        'estados': EstadoPresentacion.objects.all(),
        'form': form, 'can_edit': can_edit(request.user),
    })
