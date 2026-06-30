import re as _re
from crm.views.common import *


# ─── Doc helper ───────────────────────────────────────────────────────────────

def _save_contact_doc(f, entity_type, entity_name):
    """Guarda el fichero en CONTACT_DOCS_ROOT/<entity_type>/<entity_name>/ y devuelve la ruta."""
    slug = _re.sub(r'[^\w\-.]', '_', entity_name.strip())
    dest_dir = pathlib.Path(settings.CONTACT_DOCS_ROOT) / entity_type / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f.name
    # Si ya existe, añadir sufijo numérico
    counter = 1
    while dest_path.exists():
        stem, suffix = pathlib.Path(f.name).stem, pathlib.Path(f.name).suffix
        dest_path = dest_dir / f'{stem}_{counter}{suffix}'
        counter += 1
    with open(dest_path, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)
    return str(dest_path)


@login_required
def docs_centro(request):
    # ── Pestaña Participadas ─────────────────────────────────────────────────
    companies = visible_companies(request.user).prefetch_related('rounds', 'procesos_ma')
    participadas_data = []
    for c in companies:
        participadas_data.append({'company': c, 'total': c.documentos.count()})

    # ── Pestañas Inversores / Colaboradores ──────────────────────────────────
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    inversores_data = []
    colaboradores_data = []
    for tipo, bucket in (('Inversores', inversores_data), ('Colaboradores', colaboradores_data)):
        tipo_dir = root / tipo
        if tipo_dir.exists():
            for carpeta in sorted(tipo_dir.iterdir()):
                if carpeta.is_dir():
                    archivos = [f for f in carpeta.iterdir() if f.is_file()]
                    bucket.append({
                        'nombre': carpeta.name.replace('_', ' '),
                        'slug':   carpeta.name,
                        'count':  len(archivos),
                        'url':    reverse('crm:docs_contactos_carpeta',
                                         args=(tipo.lower(), carpeta.name)),
                    })

    tab = request.GET.get('tab', 'participadas')
    return render(request, 'crm/docs_centro.html', {
        'active_nav':        'docs_centro',
        'participadas_data': participadas_data,
        'inversores_data':   inversores_data,
        'colaboradores_data': colaboradores_data,
        'active_tab':        tab,
    })


@login_required
def docs_company(request, company_pk):
    companies = visible_companies(request.user)
    company = get_object_or_404(Company, pk=company_pk)
    if company not in companies:
        return HttpResponseForbidden()

    rounds = company.rounds.all()
    procesos = company.procesos_ma.all()
    base_qs = company.documentos.filter(round=None, proceso_ma=None)
    general_count = base_qs.filter(carpeta='general').count()

    carpetas = [
        {'label': 'General', 'icon': 'bi-folder2', 'count': general_count,
         'url': reverse('crm:docs_carpeta', args=(company_pk, 'general', 0))},
    ]
    for r in rounds:
        carpetas.append({'label': r.type, 'icon': 'bi-graph-up-arrow',
                         'count': r.documentos.count(),
                         'url': reverse('crm:docs_carpeta', args=(company_pk, 'ronda', r.pk))})
    for p in procesos:
        carpetas.append({'label': p.nombre, 'icon': 'bi-briefcase',
                         'count': p.documentos.count(),
                         'url': reverse('crm:docs_carpeta', args=(company_pk, 'ma', p.pk))})

    return render(request, 'crm/docs_company.html', {
        'active_nav': 'docs_centro',
        'company': company,
        'carpetas': carpetas,
    })


@login_required
def docs_carpeta(request, company_pk, tipo, ref_pk):
    companies = visible_companies(request.user)
    company = get_object_or_404(Company, pk=company_pk)
    if company not in companies:
        return HttpResponseForbidden()

    round_obj = proceso_obj = None
    if tipo == 'ronda':
        round_obj = get_object_or_404(Round, pk=ref_pk, company=company)
        docs = Documento.objects.filter(company=company, round=round_obj)
        carpeta_label = round_obj.type
    elif tipo == 'ma':
        proceso_obj = get_object_or_404(ProcesoMA, pk=ref_pk, company=company)
        docs = Documento.objects.filter(company=company, proceso_ma=proceso_obj)
        carpeta_label = proceso_obj.nombre
    elif tipo in ('emails', 'reuniones', 'notas'):
        docs = Documento.objects.filter(company=company, round=None, proceso_ma=None, carpeta=tipo)
        carpeta_label = tipo.capitalize()
    else:
        docs = Documento.objects.filter(company=company, round=None, proceso_ma=None, carpeta='general')
        carpeta_label = 'General'

    if request.method == 'POST':
        f = request.FILES.get('file')
        if f:
            doc = Documento(
                company=company,
                round=round_obj,
                proceso_ma=proceso_obj,
                carpeta=tipo if tipo in ('emails', 'reuniones', 'notas') else 'general',
                file=f,
                name=request.POST.get('name', '').strip() or f.name,
                description=request.POST.get('description', '').strip(),
                uploaded_by=request.user,
            )
            doc.save()
        return redirect(request.path)

    return render(request, 'crm/docs_carpeta.html', {
        'active_nav': 'docs_centro',
        'company': company,
        'carpeta_label': carpeta_label,
        'tipo': tipo,
        'ref_pk': ref_pk,
        'docs': docs,
        'round_obj': round_obj,
        'proceso_obj': proceso_obj,
    })


@login_required
def docs_delete(request, doc_pk):
    doc = get_object_or_404(Documento, pk=doc_pk)
    company = doc.company
    companies = visible_companies(request.user)
    if company not in companies:
        return HttpResponseForbidden()
    if not can_edit(request.user):
        return HttpResponseForbidden()
    tipo = 'ronda' if doc.round_id else ('ma' if doc.proceso_ma_id else 'general')
    ref_pk = doc.round_id or doc.proceso_ma_id or 0
    if request.method == 'POST':
        if doc.file:
            import os
            try:
                os.remove(doc.file.path)
            except FileNotFoundError:
                pass
        doc.delete()
    return redirect('crm:docs_carpeta', company_pk=company.pk, tipo=tipo, ref_pk=ref_pk)


@login_required
def docs_contactos(request):
    """Lista las carpetas de inversores y colaboradores en CONTACT_DOCS_ROOT."""
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    entidades = []
    for tipo in ('Inversores', 'Colaboradores'):
        tipo_dir = root / tipo
        if tipo_dir.exists():
            for carpeta in sorted(tipo_dir.iterdir()):
                if carpeta.is_dir():
                    archivos = [f for f in carpeta.iterdir() if f.is_file()]
                    entidades.append({
                        'tipo':   tipo,
                        'nombre': carpeta.name.replace('_', ' '),
                        'slug':   carpeta.name,
                        'count':  len(archivos),
                        'url':    reverse('crm:docs_contactos_carpeta',
                                         args=(tipo.lower(), carpeta.name)),
                    })
    return render(request, 'crm/docs_contactos.html', {
        'active_nav': 'docs_contactos',
        'entidades':  entidades,
        'root':       str(root),
    })


@login_required
def docs_contactos_carpeta(request, tipo, slug):
    """Lista los archivos dentro de CONTACT_DOCS_ROOT/<tipo>/<slug>/."""
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    carpeta = root / tipo.capitalize() / slug
    carpeta.mkdir(parents=True, exist_ok=True)

    if request.method == 'POST' and can_edit(request.user):
        fname = request.POST.get('delete_file', '')
        target = carpeta / pathlib.Path(fname).name
        if target.exists() and target.parent == carpeta:
            target.unlink()
        return redirect(request.path)

    archivos = sorted(
        [f for f in carpeta.iterdir() if f.is_file()],
        key=lambda f: f.stat().st_mtime, reverse=True
    )

    # Buscar qué log referencia cada archivo para poder enlazar a la cronología
    from crm.models import InvestorLog, ColaboradorLog, Investor, Colaborador as ColaboradorModel
    es_inversor = tipo.lower() == 'inversores'
    LogModel = InvestorLog if es_inversor else ColaboradorLog
    fk_field  = 'investor_id' if es_inversor else 'colaborador_id'
    detail_name = 'crm:investor_detail' if es_inversor else 'crm:colaborador_detail'

    # Resolver el PK de la entidad para el link al detalle
    entity_pk = None
    entity_detail_url = None
    if es_inversor:
        inv = Investor.objects.filter(name__iexact=slug.replace('_', ' ')).first()
        if not inv:
            inv = Investor.objects.filter(name__regex=rf'^{slug.replace("_", ".?")}$').first()
        if inv:
            entity_pk = inv.pk
            entity_detail_url = reverse('crm:investor_detail', args=[inv.pk])
    else:
        col = ColaboradorModel.objects.filter(name__iexact=slug.replace('_', ' ')).first()
        if not col:
            col = ColaboradorModel.objects.filter(name__regex=rf'^{slug.replace("_", ".?")}$').first()
        if col:
            entity_pk = col.pk
            entity_detail_url = reverse('crm:colaborador_detail', args=[col.pk])

    # Carga todos los logs de este slug que tengan attachment_url
    logs_con_adjunto = {
        l.attachment_url.rsplit('/', 1)[-1]: l
        for l in LogModel.objects.filter(attachment_url__icontains=slug)
        if l.attachment_url
    }

    files_data = []
    for f in archivos:
        log = logs_con_adjunto.get(f.name)
        cronologia_url = None
        if log:
            epk = getattr(log, fk_field)
            cronologia_url = reverse(detail_name, args=[epk]) + f'#log-{log.pk}'
        files_data.append({
            'name':           f.name,
            'size_kb':        round(f.stat().st_size / 1024, 1),
            'url':            reverse('crm:docs_contactos_download', args=(tipo, slug, f.name)),
            'cronologia_url': cronologia_url,
        })

    return render(request, 'crm/docs_contactos_carpeta.html', {
        'active_nav':        'docs_centro',
        'tipo':              tipo.capitalize(),
        'nombre':            slug.replace('_', ' '),
        'files':             files_data,
        'can_edit':          can_edit(request.user),
        'entity_detail_url': entity_detail_url,
    })


@login_required
def docs_contactos_download(request, tipo, slug, filename):
    """Sirve un archivo del repositorio de contactos."""
    import mimetypes
    from django.http import FileResponse
    root = pathlib.Path(settings.CONTACT_DOCS_ROOT)
    safe_name = pathlib.Path(filename).name
    path = root / tipo.capitalize() / slug / safe_name
    if not path.exists() or not path.is_file():
        raise Http404
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(open(path, 'rb'), content_type=mime or 'application/octet-stream',
                        as_attachment=False, filename=safe_name)


@login_required
def parse_email(request):
    """Extrae metadatos del .msg y elimina el archivo inmediatamente (RGPD).
    El cuerpo se devuelve al browser solo para que el usuario pueda
    solicitar el resumen IA de forma explícita; el servidor no lo almacena."""
    import os, tempfile
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    f = request.FILES.get('file')
    if not f or not f.name.lower().endswith('.msg'):
        return JsonResponse({'error': 'Se esperaba un archivo .msg'}, status=400)

    with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as tmp:
        for chunk in f.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        import extract_msg
        msg      = extract_msg.Message(tmp_path)
        raw_date = msg.date
        sender   = str(msg.sender   or '').strip()
        to_field = str(msg.to       or '').strip()
        subject  = str(msg.subject  or '').strip()
        body     = str(msg.body     or '').strip()
        msg.close()
    except Exception as exc:
        return JsonResponse({'error': f'Error al leer el archivo: {exc}'}, status=400)
    finally:
        # Eliminación inmediata — cumplimiento RGPD
        os.unlink(tmp_path)

    user_email = (request.user.email or '').lower()
    if user_email and user_email in sender.lower():
        direction = 'Saliente (Out)'
    else:
        direction = 'Entrante (In)'

    # Parsear fecha — extract_msg puede devolver datetime o string
    date_str = ''
    if raw_date:
        import datetime as dt_mod
        if isinstance(raw_date, (dt_mod.datetime, dt_mod.date)):
            date_str = raw_date.strftime('%Y-%m-%d')
        else:
            # Intentar parsear como string RFC 2822 (formato email estándar)
            try:
                import email.utils
                parsed = email.utils.parsedate_to_datetime(str(raw_date))
                date_str = parsed.strftime('%Y-%m-%d')
            except Exception:
                try:
                    # Último recurso: extraer YYYY-MM-DD o DD/MM/YYYY
                    import re
                    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(raw_date))
                    if m:
                        date_str = m.group(0)
                except Exception:
                    pass

    # El texto inicial lo construye el JS a partir de los campos individuales
    summary_text = ''

    return JsonResponse({
        'date':         date_str,
        'type':         'Email',
        'direction':    direction,
        'sender':       sender,
        'to_field':     to_field,
        'subject':      subject,
    })


@login_required
def parse_contact_email(request):
    """Extrae datos de contacto de un .msg para pre-rellenar el formulario de nuevo contacto.
    Sin IA ni llamadas externas. El archivo se elimina inmediatamente (RGPD)."""
    import os, re, tempfile
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    f = request.FILES.get('file')
    if not f or not f.name.lower().endswith('.msg'):
        return JsonResponse({'error': 'Se esperaba un archivo .msg'}, status=400)

    with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as tmp:
        for chunk in f.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        import extract_msg
        msg    = extract_msg.Message(tmp_path)
        sender = str(msg.sender or '').strip()
        body   = str(msg.body   or '').strip()
        msg.close()
    except Exception as exc:
        return JsonResponse({'error': f'Error al leer el archivo: {exc}'}, status=400)
    finally:
        os.unlink(tmp_path)  # eliminación inmediata — RGPD

    # ── Extraer email del remitente ────────────────────────────────────────
    email_match = re.search(r'<([^>@\s]+@[^>]+)>', sender)
    contact_email = email_match.group(1).strip() if email_match else (
        sender if '@' in sender else ''
    )

    # ── Extraer nombre de la persona (antes de | o <) ─────────────────────
    contact_name = re.split(r'\s*[|<]', sender)[0].strip()

    # ── Extraer nombre de empresa: primero del display name, luego del dominio
    company_name = ''
    pipe_match = re.search(r'\|\s*([^<|]+?)(?:\s*<|$)', sender)
    if pipe_match:
        company_name = pipe_match.group(1).strip()
    elif contact_email and '@' in contact_email:
        domain = contact_email.split('@')[-1]
        # Quitar TLD y capitalizar (ej. "kfund.co" → "Kfund")
        company_name = domain.split('.')[0].capitalize()

    # ── Extraer teléfono del cuerpo (regex, sin IA) ───────────────────────
    contact_phone = ''
    if body:
        phone_candidates = re.findall(
            r'(?<!\d)(\+?[\d][\d\s\.\-\(\)]{7,16}[\d])(?!\d)', body
        )
        for candidate in phone_candidates:
            digits = re.sub(r'\D', '', candidate)
            if 9 <= len(digits) <= 15 and not re.match(r'^(19|20)\d{6}$', digits):
                contact_phone = candidate.strip()
                break

    # ── Extraer cargo desde la firma del email (heurística, sin IA) ───────
    contact_role = ''
    if body:
        ROLE_RE = re.compile(
            r'\b(director[a]?|gerente|presidente|ceo|cfo|cto|coo|cso|cpo|'
            r'vice[- ]?president[ae]?|vp\b|socio|partner|managing partner|'
            r'analista|analyst|manager|responsable|jefe|head of|chief|'
            r'founder|co-?founder|fundador|associate|inversor|investor|'
            r'advisor|asesor|consultor|consultant|coordinador|coordinator|'
            r'principal|ejecutiv[ao]|senior|director general|'
            r'managing director|investment manager|portfolio manager)\b',
            re.IGNORECASE,
        )
        # Buscar en la zona de firma: últimas 30 líneas o tras separador '--'
        lines = body.split('\n')
        sig_start = 0
        for i, ln in enumerate(lines):
            if ln.strip() in ('--', '- -', '—', '___'):
                sig_start = i + 1
                break
        sig_lines = lines[max(sig_start, len(lines) - 30):]

        for ln in sig_lines:
            ln = ln.strip()
            if not ln or len(ln) > 90:
                continue
            # Saltar líneas que parezcan emails, URLs o teléfonos
            if re.search(r'[@://]|\d{6,}', ln):
                continue
            # Saltar si coincide con el nombre o empresa del contacto
            if contact_name and contact_name.split()[0].lower() in ln.lower():
                continue
            if company_name and company_name.split()[0].lower() in ln.lower():
                continue
            if ROLE_RE.search(ln):
                # Limpiar separadores iniciales
                clean = re.sub(r'^[\s\|\-·•–]+', '', ln).strip()
                if 2 < len(clean) <= 80:
                    contact_role = clean
                    break

    return JsonResponse({
        'contact_name':  contact_name,
        'contact_email': contact_email,
        'contact_phone': contact_phone,
        'contact_role':  contact_role,
        'company_name':  company_name,
    })
