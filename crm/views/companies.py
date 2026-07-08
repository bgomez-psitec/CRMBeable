from crm.views.common import *


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

    group = request.GET.get('group', 'fund')
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

    cards.sort(key=lambda c: (not c['company'].int_code, c['company'].int_code, c['company'].name))

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
        'sector_opts': get_sector_opts(),
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
def company_set_field(request, pk):
    """AJAX/POST: cambia un campo agrupable de una participada (drag & drop)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    if not can_edit(request.user):
        return JsonResponse({'ok': False}, status=403)
    company = get_object_or_404(Company, pk=pk)
    field = request.POST.get('field', '')
    value = request.POST.get('value', '')
    FK_FIELDS = {
        'fund':  (Fund,            'fund'),
        'stage': (EstadoInversion, 'stage'),
    }
    CHAR_FIELDS = {'country'}
    if field in FK_FIELDS:
        model_cls, attr = FK_FIELDS[field]
        if value and value != '—':
            obj, _ = model_cls.objects.get_or_create(nombre=value)
            setattr(company, attr, obj)
        else:
            setattr(company, attr, None)
        company.save(update_fields=[attr + '_id'])
    elif field in CHAR_FIELDS:
        company.__dict__[field] = '' if value == '—' else value
        company.save(update_fields=[field])
    else:
        return JsonResponse({'ok': False, 'error': 'campo no permitido'}, status=400)
    return JsonResponse({'ok': True})


@login_required
@login_required
def company_delete(request, pk):
    if request.user.role != 'admin':
        return HttpResponseForbidden()
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        company.delete()
        messages.success(request, 'Participada eliminada.')
        return redirect('crm:companies')
    return HttpResponseForbidden()


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
        'company': company, 'sector_opts': get_sector_opts(),
    })
