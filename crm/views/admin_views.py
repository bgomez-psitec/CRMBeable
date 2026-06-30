from crm.views.common import *


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
                'estado_ma': EstadoMA, 'fase_ma': FaseMA, 'estado_colab': EstadoColaboracion,
                'relacion_colab': EtapaRelacionColaborador,
            }.get(request.POST.get('tipo'))
            if model:
                action = request.POST.get('action', '')
                if action == 'delete' or request.POST.get('delete_id'):
                    pk = request.POST.get('pk') or request.POST.get('delete_id')
                    model.objects.filter(pk=pk).delete()
                elif action == 'toggle':
                    obj = model.objects.filter(pk=request.POST.get('pk')).first()
                    if obj:
                        obj.habilitada = not obj.habilitada
                        obj.save(update_fields=['habilitada'])
                elif action == 'orden':
                    for key, val in request.POST.items():
                        if key.startswith('orden_'):
                            try:
                                model.objects.filter(pk=key.split('_')[1]).update(orden=int(val))
                            except (ValueError, IndexError):
                                pass
                elif action == 'rename':
                    nombre = request.POST.get('nombre', '').strip()
                    pk = request.POST.get('pk')
                    if nombre and pk:
                        model.objects.filter(pk=pk).update(nombre=nombre)
                else:
                    nombre = request.POST.get('nombre', '').strip()
                    if nombre:
                        model.objects.create(nombre=nombre, orden=model.objects.count())
            messages.success(request, 'Catálogo actualizado.')
        elif section == 'catalogo_crud' and request.user.role == Role.ADMIN:
            crud_model = {
                'fund': Fund, 'area': Area, 'tipo_inversor': TipoInversor,
                'etapa_inversion': EtapaInversion, 'rango_ticket': RangoTicket,
                'rango_aum': RangoAUM, 'nivel': Nivel, 'tiempo_mercado': TiempoMercado,
                'facturacion': Facturacion, 'estado_inversion': EstadoInversion,
                'sector': Sector,
            }.get(request.POST.get('tipo'))
            if crud_model:
                action = request.POST.get('action', '')
                if action == 'delete' or request.POST.get('delete_id'):
                    pk = request.POST.get('pk') or request.POST.get('delete_id')
                    crud_model.objects.filter(pk=pk).delete()
                elif action == 'toggle' or request.POST.get('toggle_id'):
                    pk = request.POST.get('pk') or request.POST.get('toggle_id')
                    obj = crud_model.objects.filter(pk=pk).first()
                    if obj:
                        obj.habilitada = not obj.habilitada
                        obj.save(update_fields=['habilitada'])
                elif action == 'orden':
                    for key, val in request.POST.items():
                        if key.startswith('orden_'):
                            try:
                                crud_model.objects.filter(pk=key.split('_')[1]).update(orden=int(val))
                            except (ValueError, IndexError):
                                pass
                elif action == 'rename':
                    nombre = request.POST.get('nombre', '').strip()
                    pk = request.POST.get('pk')
                    if nombre and pk:
                        crud_model.objects.filter(pk=pk).update(nombre=nombre)
                else:
                    nombre = request.POST.get('nombre', '').strip()
                    if nombre:
                        crud_model.objects.get_or_create(
                            nombre=nombre,
                            defaults={'orden': crud_model.objects.count()},
                        )
            messages.success(request, 'Catálogo actualizado.')
        elif section == 'provincia' and request.user.role == Role.ADMIN:
            action = request.POST.get('action')
            if action == 'create':
                nombre = request.POST.get('nombre', '').strip()
                if nombre:
                    orden = Provincia.objects.count()
                    Provincia.objects.create(nombre=nombre, orden=orden)
                    messages.success(request, 'Provincia añadida.')
            elif action == 'delete':
                Provincia.objects.filter(pk=request.POST.get('pk')).delete()
                messages.success(request, 'Provincia eliminada.')
            elif action == 'toggle':
                p = get_object_or_404(Provincia, pk=request.POST.get('pk'))
                p.habilitada = not p.habilitada
                p.save(update_fields=['habilitada'])
            elif action == 'orden':
                for key, val in request.POST.items():
                    if key.startswith('orden_'):
                        try:
                            Provincia.objects.filter(pk=key.split('_')[1]).update(orden=int(val))
                        except (ValueError, IndexError):
                            pass
                messages.success(request, 'Orden actualizado.')
            elif action == 'rename':
                nombre = request.POST.get('nombre', '').strip()
                pk = request.POST.get('pk')
                if nombre and pk:
                    Provincia.objects.filter(pk=pk).update(nombre=nombre)
                    messages.success(request, 'Provincia actualizada.')
        return redirect('crm:settings')

    return render(request, 'crm/settings.html', {
        'active_nav': 'settings',
        'estados': EstadoPresentacion.objects.all(),
        'fases': FaseRonda.objects.all(),
        'relaciones': EtapaRelacion.objects.all(),
        'estados_ma': EstadoMA.objects.all(),
        'fases_ma': FaseMA.objects.all(),
        'estados_colab': EstadoColaboracion.objects.all(),
        'relaciones_colab': EtapaRelacionColaborador.objects.all(),
        'provincias': Provincia.objects.all(),
        'cat_funds': Fund.objects.all(),
        'cat_estado_inversion': EstadoInversion.objects.all(),
        'cat_nivel': Nivel.objects.all(),
        'cat_tiempo_mercado': TiempoMercado.objects.all(),
        'cat_facturacion': Facturacion.objects.all(),
        'cat_sector': Sector.objects.all(),
        'cat_tipo_inversor': TipoInversor.objects.all(),
        'cat_etapa_inversion': EtapaInversion.objects.all(),
        'cat_rango_ticket': RangoTicket.objects.all(),
        'cat_rango_aum': RangoAUM.objects.all(),
        'cat_area': Area.objects.all(),
        'is_admin': request.user.role == Role.ADMIN,
    })
