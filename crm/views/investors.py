from crm.views.common import *
from crm.views.docs import _save_contact_doc


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

    # ── KPIs Colaboraciones ────────────────────────────────────────────────
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
def investor_set_relation(request, pk):
    if request.method == 'POST' and can_edit(request.user):
        investor = get_object_or_404(Investor, pk=pk)
        relation_id = request.POST.get('relation_id') or None
        investor.relation_id = relation_id
        investor.save(update_fields=['relation_id'])
    return redirect(request.POST.get('next', 'crm:investors'))


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
def investor_log_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    log = get_object_or_404(InvestorLog, pk=pk)
    investor_pk = log.investor_id
    if request.method == 'POST':
        log.delete()
    return redirect('crm:investor_detail', pk=investor_pk)


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
def interaction_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    interaction = get_object_or_404(Interaction, pk=pk)
    investor_pk = interaction.introduction.investor_id
    if request.method == 'POST':
        interaction.delete()
    return redirect('crm:investor_detail', pk=investor_pk)
