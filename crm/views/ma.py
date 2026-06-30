from crm.views.common import *
from crm.views.docs import _save_contact_doc


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
