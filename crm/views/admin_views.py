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
                nombre = request.POST.get('nombre', '').strip()
                if request.POST.get('delete_id'):
                    model.objects.filter(pk=request.POST['delete_id']).delete()
                elif nombre:
                    model.objects.create(nombre=nombre, orden=model.objects.count())
            messages.success(request, 'Catálogo actualizado.')
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
        'is_admin': request.user.role == Role.ADMIN,
    })
