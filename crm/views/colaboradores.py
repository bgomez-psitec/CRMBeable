import re as _re
from crm.views.common import *
from crm.views.docs import _save_contact_doc


@login_required
def colaboradores(request):
    qs = Colaborador.objects.select_related('relation').all()
    q               = request.GET.get('q', '').strip()
    tipo            = request.GET.get('tipo', '').strip()
    relacion_filter = request.GET.get('relacion', '').strip()
    sector_filter   = request.GET.get('sector', '').strip()
    view            = request.GET.get('view', 'list')

    if q:
        qs = qs.filter(name__icontains=q)
    if relacion_filter:
        qs = qs.filter(relation__nombre=relacion_filter)
    if sector_filter:
        qs = qs.filter(sectors__icontains=sector_filter)

    g1, g2, g3 = parse_groups(request.GET, COLAB_GROUP_KEYS.keys())

    cards = [
        {
            'colaborador': c,
            'activos_colab': c.colaboraciones.exclude(status__nombre__in=COLLAB_TERMINAL).count(),
            'activos_ma': c.contactos_ma.exclude(status__nombre__in=MA_TERMINAL).count(),
        }
        for c in qs
    ]

    active_groups = [g for g in (g1, g2, g3) if g]
    groups = build_groups(cards, [COLAB_GROUP_KEYS[g] for g in active_groups]) if active_groups else None

    etapas = list(EtapaRelacion.objects.all())
    pipe_stages = []
    for etapa in etapas:
        items = [c for c in cards if c['colaborador'].relation_id == etapa.pk]
        pipe_stages.append({'etapa': etapa, 'items': items})
    sin_etapa = [c for c in cards if c['colaborador'].relation_id is None]
    if sin_etapa:
        pipe_stages.insert(0, {'etapa': None, 'items': sin_etapa})

    return render(request, 'crm/colaboradores.html', {
        'active_nav': 'colaboradores', 'cards': cards, 'groups': groups,
        'group1': g1, 'group2': g2, 'group3': g3,
        'group_labels': COLAB_GROUP_LABELS,
        'q': q, 'tipo': tipo,
        'relacion_filter': relacion_filter,
        'sector_filter': sector_filter,
        'etapas_relacion': EtapaRelacion.objects.all(),
        'grado_actividad_opts': GradoActividad.objects.filter(habilitada=True),
        'sector_opts': get_sector_opts(),
        'view': view, 'pipe_stages': pipe_stages,
        'can_edit': can_edit(request.user),
    })


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
def colaborador_set_field(request, pk):
    """AJAX/POST: change a single groupable field on a colaborador."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    if not (request.user.role in ('admin', 'editor')):
        return JsonResponse({'ok': False}, status=403)
    obj = get_object_or_404(Colaborador, pk=pk)
    field = request.POST.get('field', '')
    value = request.POST.get('value', '')
    if field == 'country':
        obj.country = '' if value == '—' else value
        obj.save(update_fields=['country'])
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'error': 'campo no permitido'}, status=400)


@login_required
@login_required
def colaborador_delete(request, pk):
    if request.user.role != 'admin':
        return HttpResponseForbidden()
    obj = get_object_or_404(Colaborador, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Colaborador eliminado.')
        return redirect('crm:colaboradores')
    return HttpResponseForbidden()


def colaborador_edit(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    obj = get_object_or_404(Colaborador, pk=pk)
    if request.method == 'POST':
        obj.name = request.POST.get('name', obj.name).strip()
        obj.country = request.POST.get('country', '').strip()
        obj.sectors = ', '.join(request.POST.getlist('sectors'))
        obj.website = request.POST.get('website', '').strip()
        obj.phone = request.POST.get('phone', '').strip()
        obj.linkedin = request.POST.get('linkedin', '').strip()
        obj.notes = request.POST.get('notes', '').strip()
        relation_id = request.POST.get('relation')
        obj.relation_id = relation_id or None
        obj.grado_actividad_id = request.POST.get('grado_actividad') or None
        obj.pub_status = request.POST.get('pub_status', '').strip()
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

    chrono = []
    for log in colaborador.logs.select_related('round__company', 'proceso_ma__company', 'colaboracion__company').all():
        ctx = 'ronda' if log.round else ('ma' if log.proceso_ma else ('colaboracion' if log.colaboracion else (log.context or '')))
        company = log.round.company if log.round else (log.proceso_ma.company if log.proceso_ma else (log.colaboracion.company if log.colaboracion else None))
        if log.round:
            process_label = f'{log.round.company.name} · {log.round.type}'
        elif log.proceso_ma:
            process_label = f'{log.proceso_ma.nombre} (M&A)'
        elif log.colaboracion:
            process_label = str(log.colaboracion.descripcion or (log.colaboracion.company.name if log.colaboracion.company else ''))
        else:
            process_label = ''
        chrono.append({
            'pk': log.pk, 'id': log.pk, 'date': log.date, 'type': log.type, 'summary': log.summary,
            'created_by': log.created_by, 'attachment_url': log.attachment_url,
            'context': ctx, 'round': log.round, 'proceso_ma': log.proceso_ma,
            'colaboracion': log.colaboracion, 'company': company,
            'process_label': process_label,
        })

    if request.method == 'POST' and can_edit(request.user):
        return redirect('crm:colaborador_detail', pk=pk)

    from crm.models import ProcesoMA, Colaboracion as ColaboracionModel
    log_rounds = Round.objects.filter(introductions__colaborador=colaborador).select_related('company').distinct()
    log_ma     = ProcesoMA.objects.filter(contactos__comprador=colaborador).select_related('company').distinct()
    log_colabs = ColaboracionModel.objects.filter(colaborador=colaborador).select_related('company').distinct()

    colaborador_companies = Company.objects.filter(
        colaboraciones__colaborador=colaborador
    ).distinct()
    colab_slug = _re.sub(r'[^\w\-.]', '_', colaborador.name.strip())
    return render(request, 'crm/colaborador_detail.html', {
        'active_nav': 'colaboradores', 'colaborador': colaborador,
        'is_admin': request.user.role == 'admin',
        'colaborador_companies': colaborador_companies,
        'docs_url': reverse('crm:docs_contactos_carpeta', args=('Colaboradores', colab_slug)),
        'intros': intros, 'contactos_ma': contactos_ma, 'colabs': colabs,
        'intros_activas': intros_activas, 'intros_invertidas': intros_invertidas,
        'intros_descartadas': intros_descartadas,
        'ma_activos': ma_activos, 'ma_vendidos': ma_vendidos,
        'ma_descartados': ma_descartados, 'ma_mejor_oferta': ma_mejor_oferta,
        'colab_activas': colab_activas, 'colab_firmadas': colab_firmadas,
        'colab_descartadas': colab_descartadas,
        'chrono': chrono,
        'log_rounds': log_rounds, 'log_ma': log_ma, 'log_colabs': log_colabs,
        'etapas_relacion': EtapaRelacion.objects.all(),
        'grado_actividad_opts': GradoActividad.objects.filter(habilitada=True),
        'estado_publico_opts': EstadoPublicoInversor.objects.filter(habilitada=True),
        'sector_opts': get_sector_opts(),
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
def colaborador_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(ColaboradorLog, pk=pk)
    colaborador_pk = log.colaborador_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:colaborador_detail', pk=colaborador_pk)


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

    try:
        slug = _re.sub(r'[^\w\-.]', '_', colaborador.name.strip())
        saved_path = _save_contact_doc(f, 'Colaboradores', colaborador.name)
        actual_filename = pathlib.Path(saved_path).name
        attachment_url = reverse('crm:docs_contactos_download',
                                 args=('colaboradores', slug, actual_filename))
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

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
