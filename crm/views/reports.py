from crm.views.common import *


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
