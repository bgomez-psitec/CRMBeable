import re as _re
from crm.views.common import *
from crm.views.docs import _save_contact_doc


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
                tipo_relacion_id=request.POST.get('tipo_relacion') or None,
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

    g1, g2, g3 = parse_groups(request.GET, COLAB_PIPE_GROUP_KEYS)
    keyfns = [COLAB_PIPE_GROUP_KEYS[k] for k in (g1, g2, g3) if k]
    groups = build_groups(colaboraciones, keyfns) if keyfns else None

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
                tipo_relacion_id=request.POST.get('tipo_relacion') or None,
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
        'tipo':        lambda c: c.tipo_relacion.nombre if c.tipo_relacion else '—',
        'estado':      lambda c: c.status.nombre if c.status else '—',
    }
    COL_GRP_LABELS = [
        ('company', 'Participada'), ('colaborador', 'Colaborador'),
        ('tipo', 'Tipo'), ('estado', 'Estado'),
    ]

    g1, g2, g3 = parse_groups(request.GET, COL_GRP_KEYS.keys())
    active_g = [g for g in (g1, g2, g3) if g]
    colaboraciones = list(qs)
    groups = build_groups(colaboraciones, [COL_GRP_KEYS[g] for g in active_g]) if active_g else None

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
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'all_investors': visible_investors(request.user).order_by('name'),
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
    from accounts.models import Role
    contact_name = col.colaborador.name if col.colaborador else (col.investor.name if col.investor else col.company.name)
    return render(request, 'crm/colaboracion_form.html', {
        'active_nav': 'companies', 'form': form, 'company': col.company,
        'title': f'Editar colaboración — {contact_name}',
        'colaboracion': col,
        'is_admin': request.user.role == Role.ADMIN,
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'all_investors': visible_investors(request.user).order_by('name'),
    })


@login_required
def colaboracion_delete(request, pk):
    from accounts.models import Role
    col = get_object_or_404(Colaboracion.objects.select_related('company'), pk=pk)
    if request.user.role != Role.ADMIN or not can_see_company(request.user, col.company_id):
        return HttpResponseForbidden()
    if request.method == 'POST':
        company_pk = col.company_id
        col.delete()
        messages.success(request, 'Colaboración eliminada.')
        return redirect('crm:company_detail', pk=company_pk)
    return HttpResponseForbidden()


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
        'all_companies': visible_companies(request.user).order_by('name'),
        'all_colaboradores': Colaborador.objects.order_by('name'),
        'all_investors': visible_investors(request.user).order_by('name'),
        'tipos_relacion_colab': TipoRelacionColaboracion.objects.filter(habilitada=True),
    })


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
        tipo_raw = request.POST.get('tipo_relacion', '').strip()
        col.tipo_relacion_id = int(tipo_raw) if tipo_raw.isdigit() else None
        col.date        = request.POST.get('date', '').strip() or None
        col.intro_by    = request.POST.get('intro_by', '').strip()
        col.next_action = request.POST.get('next_action', '').strip()
        col.next_date   = request.POST.get('next_date', '').strip() or None
        col.descripcion = request.POST.get('descripcion', '').strip()
        new_company_id = request.POST.get('company_id') or None
        if new_company_id and can_see_company(request.user, new_company_id):
            col.company_id = new_company_id
        new_colaborador_id = request.POST.get('colaborador_id') or None
        new_investor_id    = request.POST.get('investor_id') or None
        if new_colaborador_id:
            col.colaborador_id = new_colaborador_id
            col.investor_id = None
        elif new_investor_id:
            col.investor_id = new_investor_id
            col.colaborador_id = None
        col.save(update_fields=['status_id', 'tipo_relacion_id', 'date', 'intro_by',
                                'next_action', 'next_date', 'descripcion', 'company_id',
                                'colaborador_id', 'investor_id'])

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
def colaboracion_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    from crm.models import InteraccionColaboracion
    log = get_object_or_404(InteraccionColaboracion, pk=pk)
    col_pk = log.colaboracion_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:colaboracion_detail', pk=col_pk)


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
