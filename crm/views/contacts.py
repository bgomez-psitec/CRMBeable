from crm.views.common import *


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
