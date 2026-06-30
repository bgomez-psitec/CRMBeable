from crm.views.common import *


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
def inbox_delete(request, pk):
    if not can_edit(request.user):
        return HttpResponseForbidden()
    msg = get_object_or_404(InboxMessage, pk=pk)
    if request.method == 'POST':
        msg.delete()
        messages.success(request, 'Email eliminado.')
    return redirect('crm:inbox')
