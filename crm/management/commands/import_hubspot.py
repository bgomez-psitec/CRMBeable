"""
Comando de importación de HubSpot → CRM Beable.

Uso:
    python manage.py import_hubspot            # dry-run (sin tocar la BD)
    python manage.py import_hubspot --execute  # importación real
    python manage.py import_hubspot --only companies
    python manage.py import_hubspot --only contacts
    python manage.py import_hubspot --only deals
    python manage.py import_hubspot --only activities

Genera un CSV de revisión en logs/hubspot_import_review.csv con los registros
que necesitan atención manual.
"""

import csv
import difflib
import os
import pathlib
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

import hubspot
from hubspot.crm.companies import ApiException as CompanyApiException

# ── Mapeo de tipos de empresa ────────────────────────────────────────────────

COMPANY_TYPE_MAP = {
    'Start-Up':    'company',
    'Co-Inversor': 'investor',
}
COLABORADOR_RELATION_MAP = {
    'LP/Inversor': 'LP/Inversor',
    'PARTNER':     'Colaborador',
    'Corporate':   'Corporate',
    'Cliente':     'Cliente',
    'Proveedor':   'Proveedor',
    'OPI':         'OPI',
    'PROSPECT':    'Prospect',
    'OTHER':       'Otro',
}

DEAL_LINE_MAP = {
    'linea_a':                     'round',
    'linea_b':                     'round',
    'Venta Participadas':          'proceso_ma',
    'Colaboraciones Participadas': 'colaboracion',
}

ACTIVITY_TYPE_MAP = {
    'NOTE':    'Nota',
    'EMAIL':   'Email',
    'CALL':    'Llamada',
    'MEETING': 'Reunión',
    'TASK':    'Nota',
}

# ── Mapeo de enfoque_de_inversion → Sector CRM ──────────────────────────────

SECTOR_MAP = {
    'AM':                          ['Advanced Materials'],
    'Nanotechnology':              ['Nanotechnology'],
    'Micro & Nanoectronics':       ['Microelectronics or Nanoelectronics'],
    'Photonics':                   ['Photonics'],
    'Industrial Biotechnology':    ['Industrial Biotechnology'],
    'AMF':                         ['Advanced Manufacturing and Processing'],
    'Pharmaceutical Ingredients':  ['Pharma'],
    'AI':                          ['Artificial Intelligence', 'Data Mining'],
    'Other ICT':                   ['Other ICT'],
    'Integration of technologies': ['Other'],
    'Other':                       ['Other'],
}

# ── Mapeo de dealstage (etiqueta HubSpot) → estado CRM ─────────────────────

# Fundraising (linea_a / linea_b) → EstadoPresentacion (en Introduction)
HS_STAGE_TO_PRESENTACION = {
    'Lead Posible':                        'Lead Posible. No contactado',
    'Primer Contacto (Envío Deck)':        'Primer Contacto (Envío Deck)',
    'Reunión Presentación Deck (CIA)':     'Reunión Presentación Deck (CIA)',
    'Reunión Presentación Deck (Interna)': 'Reunión Presentación Deck (Interna)',
    'Reuniones de cierre condiciones':     'Reuniones de cierre condiciones',
    'Proceso de firma de Term Sheet':      'Proceso de firma de Term Sheet',
    'Inversión no realizada':              'Descartado',
}

# Venta Participadas → FaseMA (creado con get_or_create si no existe)
HS_STAGE_TO_FASE_MA = {
    'Lead Posible':                        'Lead Posible. No contactado',
    'Reunión Presentación Deck (Interna)': 'Reunión Presentación Deck (Interna)',
    'Reunión Presentación Deck (CIA)':     'Reunión Presentación Deck (CIA)',
    'Inversión no realizada':              'Descartado',
}

# Colaboraciones Participadas → EstadoColaboracion
HS_STAGE_TO_COLABORACION = {
    'Lead Posible':                            'Lead Posible. No contactado',
    'Primer Contacto (Envío Deck)':            'Contactado',
    'Reunión Presentación Deck (Interna)':     'Reunión',
    'Negociado Acuerdo de Colaboración':       'Negociación',
    'Acuerdo/ Venta Cerrada / Proceso firma':  'Obtenido / Proceso de firma de Acuerdo',
    'Acuerdo/ Venta no Cerrada':               'Descartado',
    'Inversión no realizada':                  'Descartado',
    'Reuniones de cierre condiciones':         'Negociación',
}


class Command(BaseCommand):
    help = 'Importa datos desde HubSpot (dry-run por defecto, --execute para guardar)'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true',
                            help='Ejecutar la importación real (por defecto solo dry-run)')
        parser.add_argument('--flush', action='store_true',
                            help='Eliminar todos los datos CRM antes de importar (requiere --execute)')
        parser.add_argument('--only', choices=['companies', 'contacts', 'deals', 'activities'],
                            help='Ejecutar solo una fase')

    def handle(self, *args, **options):
        self.dry_run  = not options['execute']
        self.only     = options.get('only')
        self.do_flush = options.get('flush', False)
        self.review   = []
        self.stats    = {k: 0 for k in ['companies', 'investors', 'colaboradores',
                                         'contacts', 'rounds', 'procesos_ma',
                                         'colaboraciones', 'activities', 'skipped', 'errors']}

        token = os.environ.get('HUBSPOT_TOKEN') or getattr(settings, 'HUBSPOT_TOKEN', '')
        if not token:
            self.stderr.write('ERROR: HUBSPOT_TOKEN no configurado en .env')
            return

        self.client = hubspot.HubSpot(access_token=token)

        import io
        if hasattr(self.stdout, '_out'):
            try:
                self.stdout._out = io.TextIOWrapper(
                    self.stdout._out.buffer, encoding='utf-8', errors='replace')
            except Exception:
                pass

        def safe(s):
            return str(s).encode('utf-8', 'replace').decode('utf-8')
        self._safe = safe

        mode = 'DRY-RUN' if self.dry_run else 'EJECUCION REAL'
        self.stdout.write(self.style.WARNING(f'\n=== IMPORTACION HUBSPOT - {mode} ===\n'))

        from crm.models import (
            Company, Investor, Colaborador, InvestorContact, ColaboradorContacto,
            Round, ProcesoMA, Colaboracion, InvestorLog, ColaboradorLog,
            EtapaRelacionColaborador, EstadoPresentacion, EstadoMA, EstadoColaboracion,
        )
        from accounts.models import User
        self.models = {
            'Company': Company, 'Investor': Investor, 'Colaborador': Colaborador,
            'InvestorContact': InvestorContact, 'ColaboradorContacto': ColaboradorContacto,
            'Round': Round, 'ProcesoMA': ProcesoMA, 'Colaboracion': Colaboracion,
            'InvestorLog': InvestorLog, 'ColaboradorLog': ColaboradorLog,
            'EtapaRelacionColaborador': EtapaRelacionColaborador,
        }

        self.hs_company_map  = {}
        self.hs_investor_map = {}
        self.hs_colab_map    = {}
        self._dry_companies  = set()
        self._dry_investors  = set()
        self._dry_colabs     = set()

        # Cargar stages de pipelines una sola vez
        self._pipeline_stages = self._load_pipeline_stages()

        if self.do_flush:
            if self.dry_run:
                self.stdout.write(self.style.WARNING('  [--flush ignorado en dry-run]'))
            else:
                self._flush_db()

        if not self.only or self.only == 'companies':
            self._import_companies()
        if not self.only or self.only == 'contacts':
            self._import_contacts()
        if not self.only or self.only == 'deals':
            self._import_deals()
        if not self.only or self.only == 'activities':
            self._import_activities()

        self._write_review_csv()
        self._print_summary()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _load_pipeline_stages(self):
        """Carga stage_id → label desde la API de pipelines de HubSpot."""
        stage_map = {}
        try:
            pipelines = self.client.crm.pipelines.pipelines_api.get_all(object_type='deals')
            for pipeline in pipelines.results:
                for stage in pipeline.stages:
                    stage_map[stage.id] = stage.label
            self.stdout.write(f'  Pipeline stages cargados: {len(stage_map)}')
        except Exception as e:
            self.stdout.write(f'  [WARN] No se pudieron cargar pipeline stages: {str(e)[:120]}')
        return stage_map

    def _normalize_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    def _parse_date(self, val):
        if not val:
            return None
        try:
            return datetime.fromisoformat(str(val)[:10]).date()
        except Exception:
            return None

    def _parse_amount(self, val):
        if not val:
            return None
        try:
            return Decimal(str(val))
        except InvalidOperation:
            return None

    def _map_sectors(self, hs_value):
        """Convierte enfoque_de_inversion (multi-valor ;) a lista de nombres CRM."""
        if not hs_value:
            return []
        result = []
        for part in hs_value.split(';'):
            part = part.strip()
            if not part:
                continue
            mapped = SECTOR_MAP.get(part, [part])
            result.extend(mapped)
        seen = set()
        out = []
        for s in result:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    # ── Limpieza de BD ──────────────────────────────────────────────────────

    def _flush_db(self):
        from crm.models import (
            Company, Investor, Colaborador, Round, ProcesoMA, Colaboracion,
            Introduction, Interaction, ContactoMA, InteraccionMA, InteraccionColaboracion,
            InvestorLog, ColaboradorLog, InvestorContact, ColaboradorContacto,
            InboxMessage, Documento, RoundFaseLog, ProcesoMAFaseLog,
        )
        self.stdout.write(self.style.WARNING('\n  Eliminando datos existentes...'))
        models_to_flush = [
            InboxMessage, Interaction, InteraccionMA, InteraccionColaboracion,
            InvestorLog, ColaboradorLog, RoundFaseLog, ProcesoMAFaseLog,
            Introduction, ContactoMA, Colaboracion,
            Round, ProcesoMA,
            InvestorContact, ColaboradorContacto,
            Documento,
            Investor, Colaborador, Company,
        ]
        for m in models_to_flush:
            count = m.objects.count()
            m.objects.all().delete()
            self.stdout.write(f'  Eliminados {count:4d} registros de {m.__name__}')
        self.stdout.write(self.style.SUCCESS('  BD limpia.\n'))

    # ── FASE 1: Empresas ────────────────────────────────────────────────────

    def _import_companies(self):
        self.stdout.write('\n[1/4] Importando Empresas...')
        props = ['name', 'type', 'country', 'city', 'phone', 'website',
                 'linkedin_company_page', 'category_of_investor', 'enfoque_de_inversion',
                 'description', 'hs_object_id']
        after = None
        total = 0

        while True:
            res = self.client.crm.companies.basic_api.get_page(
                limit=100, after=after, properties=props,
                associations=['contacts', 'deals'])
            for c in res.results:
                self._process_company(c)
                total += 1
            if not res.paging or not res.paging.next:
                break
            after = res.paging.next.after

        self.stdout.write(f'  → {total} empresas procesadas en HubSpot')

    def _process_company(self, hs_obj):
        p     = hs_obj.properties
        hs_id = p.get('hs_object_id', '')
        name  = (p.get('name') or '').strip()
        tipo  = (p.get('type') or '').strip()

        if not name:
            return

        dest = COMPANY_TYPE_MAP.get(tipo, 'colaborador')

        if dest == 'company':
            self._upsert_company(hs_id, name, p)
        elif dest == 'investor':
            self._upsert_investor(hs_id, name, p)
        else:
            relacion_label = COLABORADOR_RELATION_MAP.get(tipo, tipo)
            self._upsert_colaborador(hs_id, name, p, relacion_label)

    def _upsert_company(self, hs_id, name, p):
        from crm.models import Company
        if not self.dry_run:
            obj, created = Company.objects.get_or_create(
                name=name,
                defaults={
                    'country':  p.get('country') or '',
                    'website':  self._normalize_url(p.get('website') or ''),
                    'phone':    p.get('phone') or '',
                    'linkedin': self._normalize_url(p.get('linkedin_company_page') or ''),
                }
            )
            self.hs_company_map[hs_id] = obj
            if created:
                self.stats['companies'] += 1
                self.stdout.write(f'  [Participada] {name} (NUEVA)')
        else:
            if name not in self._dry_companies:
                self._dry_companies.add(name)
                self.stats['companies'] += 1
                self.stdout.write(f'  [Participada] {name}')

    def _upsert_investor(self, hs_id, name, p):
        from crm.models import Investor, TipoInversor
        if not self.dry_run:
            # Resolver TipoInversor
            inv_type = None
            cat_str = (p.get('category_of_investor') or '').strip()
            if cat_str:
                inv_type, _ = TipoInversor.objects.get_or_create(
                    nombre=cat_str,
                    defaults={'orden': TipoInversor.objects.count()}
                )

            # Resolver sectores
            sectors = self._map_sectors(p.get('enfoque_de_inversion') or '')

            obj, created = Investor.objects.get_or_create(
                name=name,
                defaults={
                    'country':  p.get('country') or '',
                    'website':  self._normalize_url(p.get('website') or ''),
                    'phone':    p.get('phone') or '',
                    'linkedin': self._normalize_url(p.get('linkedin_company_page') or ''),
                    'notes':    p.get('description') or '',
                    'type':     inv_type,
                    'sectors':  ', '.join(sectors),
                }
            )
            self.hs_investor_map[hs_id] = obj
            if created:
                self.stats['investors'] += 1
                self.stdout.write(f'  [Inversor]    {name} (NUEVO)')
        else:
            if name not in self._dry_investors:
                self._dry_investors.add(name)
                self.stats['investors'] += 1
                self.stdout.write(f'  [Inversor]    {name}')

    def _upsert_colaborador(self, hs_id, name, p, relacion_label):
        from crm.models import Colaborador, EtapaRelacionColaborador
        if not self.dry_run:
            relacion, _ = EtapaRelacionColaborador.objects.get_or_create(
                nombre=relacion_label,
                defaults={'orden': EtapaRelacionColaborador.objects.count()}
            )
            sectors = self._map_sectors(p.get('enfoque_de_inversion') or '')

            obj, created = Colaborador.objects.get_or_create(
                name=name,
                defaults={
                    'country':  p.get('country') or '',
                    'website':  self._normalize_url(p.get('website') or ''),
                    'phone':    p.get('phone') or '',
                    'linkedin': self._normalize_url(p.get('linkedin_company_page') or ''),
                    'notes':    p.get('description') or '',
                    'sectors':  ', '.join(sectors),
                    'relation': relacion,
                }
            )
            self.hs_colab_map[hs_id] = obj
            if created:
                self.stats['colaboradores'] += 1
                self.stdout.write(f'  [Colaborador] {name} / {relacion_label} (NUEVO)')
        else:
            if name not in self._dry_colabs:
                self._dry_colabs.add(name)
                self.stats['colaboradores'] += 1
                self.stdout.write(f'  [Colaborador] {name} / {relacion_label}')

    # ── FASE 2: Contactos ───────────────────────────────────────────────────

    def _import_contacts(self):
        self.stdout.write('\n[2/4] Importando Contactos...')
        props = ['firstname', 'lastname', 'email', 'phone', 'jobtitle',
                 'hs_object_id', 'associatedcompanyid']
        after = None
        total = 0

        while True:
            res = self.client.crm.contacts.basic_api.get_page(
                limit=100, after=after, properties=props,
                associations=['companies'])
            for c in res.results:
                self._process_contact(c)
                total += 1
            if not res.paging or not res.paging.next:
                break
            after = res.paging.next.after

        self.stdout.write(f'  → {total} contactos procesados en HubSpot')

    def _process_contact(self, hs_obj):
        from crm.models import InvestorContact, ColaboradorContacto
        p     = hs_obj.properties
        name  = f"{p.get('firstname') or ''} {p.get('lastname') or ''}".strip()
        email = p.get('email') or ''
        phone = p.get('phone') or ''
        role  = p.get('jobtitle') or ''

        if not name:
            return

        company_hs_id = None
        if hs_obj.associations and hs_obj.associations.get('companies'):
            assocs = hs_obj.associations['companies'].results
            if assocs:
                company_hs_id = str(assocs[0].id)

        if not company_hs_id:
            self.review.append({
                'tipo': 'Contacto sin empresa', 'nombre': name,
                'email': email, 'detalle': 'No tiene empresa asociada en HubSpot'
            })
            return

        investor    = self.hs_investor_map.get(company_hs_id)
        colaborador = self.hs_colab_map.get(company_hs_id)

        if investor:
            self.stdout.write(f'  [InvContacto] {name} → {investor.name}')
            if not self.dry_run:
                InvestorContact.objects.get_or_create(
                    investor=investor, name=name,
                    defaults={'email': email, 'phone': phone, 'role': role}
                )
            self.stats['contacts'] += 1
        elif colaborador:
            self.stdout.write(f'  [ColContacto] {name} → {colaborador.name}')
            if not self.dry_run:
                ColaboradorContacto.objects.get_or_create(
                    colaborador=colaborador, name=name,
                    defaults={'email': email, 'phone': phone, 'role': role}
                )
            self.stats['contacts'] += 1
        else:
            self.review.append({
                'tipo': 'Contacto sin match', 'nombre': name,
                'email': email,
                'detalle': f'Empresa HS {company_hs_id} no importada como Inversor/Colaborador'
            })

    # ── FASE 3: Deals ───────────────────────────────────────────────────────

    def _import_deals(self):
        self.stdout.write('\n[3/4] Importando Deals (Negocios)...')
        props = ['dealname', 'linea_de_negocio', 'nombre_de_la_linea_de_negocio',
                 'sociedad_asociada', 'dealstage', 'amount', 'closedate',
                 'createdate', 'description', 'hs_object_id']
        after = None
        total = 0

        while True:
            res = self.client.crm.deals.basic_api.get_page(
                limit=100, after=after, properties=props,
                associations=['companies', 'contacts'])
            for d in res.results:
                self._process_deal(d)
                total += 1
            if not res.paging or not res.paging.next:
                break
            after = res.paging.next.after

        self.stdout.write(f'  → {total} deals procesados en HubSpot')

    def _process_deal(self, hs_obj):
        p        = hs_obj.properties
        hs_id    = p.get('hs_object_id', '')
        dealname = (p.get('dealname') or '').strip()
        linea    = (p.get('linea_de_negocio') or '').strip()
        nombre   = (p.get('nombre_de_la_linea_de_negocio') or dealname).strip()
        dest     = DEAL_LINE_MAP.get(linea)

        if not dest:
            self.review.append({
                'tipo': 'Deal sin línea de negocio', 'nombre': dealname,
                'detalle': f'linea_de_negocio={linea!r}'
            })
            return

        sociedad = (p.get('sociedad_asociada') or '').strip()
        company  = self._find_company(sociedad)

        if not company and not self.dry_run:
            self.review.append({
                'tipo': 'Deal sin participada', 'nombre': dealname,
                'detalle': f'sociedad_asociada={sociedad!r}'
            })
            return

        if not company and self.dry_run and not sociedad:
            self.review.append({
                'tipo': 'Deal sin participada', 'nombre': dealname,
                'detalle': 'Sin sociedad_asociada'
            })
            return

        partner = self._find_partner_for_deal(hs_obj, dealname)

        if dest == 'round':
            self._upsert_round(hs_id, nombre, company, partner, p)
        elif dest == 'proceso_ma':
            self._upsert_proceso_ma(hs_id, nombre, company, partner, p)
        elif dest == 'colaboracion':
            self._upsert_colaboracion(hs_id, nombre, company, partner, p)

    def _sociedad_to_name(self, sociedad):
        import re
        return re.sub(r'^[A-Z0-9]+\.\d+\.\d+\s+', '', sociedad).strip()

    def _find_company(self, sociedad):
        from crm.models import Company
        if not sociedad:
            return None
        name = self._sociedad_to_name(sociedad)
        obj = Company.objects.filter(name__iexact=name).first()
        if obj:
            return obj
        obj = Company.objects.filter(name__iexact=sociedad).first()
        if obj:
            return obj
        names   = list(Company.objects.values_list('name', flat=True))
        matches = difflib.get_close_matches(name, names, n=1, cutoff=0.5)
        if matches:
            return Company.objects.filter(name=matches[0]).first()
        if not self.dry_run:
            obj, created = Company.objects.get_or_create(name=name)
            if created:
                self.stats['companies'] += 1
                self.stdout.write(f'  [Nueva Partic.] {name} (desde deal)')
            return obj
        else:
            if name not in self._dry_companies:
                self._dry_companies.add(name)
                self.stats['companies'] += 1
                self.stdout.write(f'  [Nueva Partic.] {name} (desde deal)')
            return None

    # Sufijos corporativos a eliminar antes de comparar
    _CORP_SUFFIXES = (
        r'\bS\.?\s*A\.?\s*$', r'\bS\.?\s*L\.?\s*$', r'\bS\.?\s*A\.?\s*U\.?\s*$',
        r'\bLtd\.?\s*$', r'\bLLC\.?\s*$', r'\bGmbH\.?\s*$', r'\bInc\.?\s*$',
        r'\bFund\s+\w+\s*$', r'\bFund\s*$', r'\bCapital\s*$',
        r'\bPartners\s*$', r'\bVentures\s*$', r'\bGroup\s*$',
    )

    def _normalize_name(self, name):
        import re, unicodedata
        n = name.strip()
        for pat in self._CORP_SUFFIXES:
            n = re.sub(pat, '', n, flags=re.IGNORECASE).strip()
        n = re.sub(r'[^\w\s]', ' ', n)
        n = re.sub(r'\s+', ' ', n).strip().lower()
        n = unicodedata.normalize('NFKD', n)
        return ''.join(c for c in n if not unicodedata.combining(c))

    def _fuzzy_partner_match(self, candidate, inv_names, col_names, cutoff=0.65):
        if not candidate or len(candidate) < 3:
            return None, None

        norm_cand = self._normalize_name(candidate)
        norm_inv  = {self._normalize_name(n): n for n in inv_names}
        norm_col  = {self._normalize_name(n): n for n in col_names}

        inv_match = difflib.get_close_matches(norm_cand, norm_inv.keys(), n=1, cutoff=cutoff)
        col_match = difflib.get_close_matches(norm_cand, norm_col.keys(), n=1, cutoff=cutoff)

        best_inv = (norm_inv[inv_match[0]], difflib.SequenceMatcher(None, norm_cand, inv_match[0]).ratio()) if inv_match else (None, 0)
        best_col = (norm_col[col_match[0]], difflib.SequenceMatcher(None, norm_cand, col_match[0]).ratio()) if col_match else (None, 0)

        if best_inv[1] >= best_col[1] and best_inv[0]:
            return 'investor', best_inv[0]
        if best_col[0]:
            return 'colaborador', best_col[0]
        return None, None

    _GENERIC_TOKENS = {
        'deal', 'deals', 'colaboracion', 'colaboración', 'collab',
        'negocio', 'negocios', 'ronda', 'inversion', 'inversión',
        'fund', 'funds', 'round', 'contact', 'contacto', 'meeting',
        'call', 'note', 'email', 'new', 'nuevo', 'nueva', 'test',
    }

    def _extract_deal_candidates(self, dealname):
        import re, unicodedata

        def is_generic(token):
            norm = unicodedata.normalize('NFKD', token.lower())
            norm = ''.join(c for c in norm if not unicodedata.combining(c))
            return norm in self._GENERIC_TOKENS

        parts       = re.split(r'\s*[-–/|:]\s*', dealname)
        non_generic = [p.strip() for p in parts if len(p.strip()) >= 4 and not is_generic(p.strip())]

        candidates = list(non_generic)
        for i in range(len(non_generic) - 1):
            combo = (non_generic[i] + ' ' + non_generic[i + 1]).strip()
            if combo not in candidates:
                candidates.append(combo)
        if len(parts) == 1 and not is_generic(dealname.strip()):
            if dealname.strip() not in candidates:
                candidates.append(dealname.strip())

        seen   = set()
        result = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def _find_partner_for_deal(self, hs_obj, dealname):
        from crm.models import Investor, Colaborador

        if hs_obj.associations and hs_obj.associations.get('companies'):
            for assoc in hs_obj.associations['companies'].results:
                hs_id = str(assoc.id)
                if hs_id in self.hs_investor_map:
                    return ('investor', self.hs_investor_map[hs_id])
                if hs_id in self.hs_colab_map:
                    return ('colaborador', self.hs_colab_map[hs_id])

        if self.dry_run:
            inv_names = list(self._dry_investors)
            col_names = list(self._dry_colabs)
        else:
            inv_names = list(Investor.objects.values_list('name', flat=True))
            col_names = list(Colaborador.objects.values_list('name', flat=True))

        if not inv_names and not col_names:
            self.review.append({
                'tipo': 'Deal — partner no encontrado', 'nombre': dealname,
                'detalle': 'No hay inversores/colaboradores cargados aún'
            })
            return None

        candidates = self._extract_deal_candidates(dealname)
        for candidate in candidates:
            kind, matched_name = self._fuzzy_partner_match(candidate, inv_names, col_names)
            if kind == 'investor':
                obj = None if self.dry_run else Investor.objects.filter(name=matched_name).first()
                self.review.append({
                    'tipo': 'Deal — partner por fuzzy', 'nombre': dealname,
                    'detalle': f'"{candidate}" → Inversor "{matched_name}" (revisar)'
                })
                return ('investor', obj)
            if kind == 'colaborador':
                obj = None if self.dry_run else Colaborador.objects.filter(name=matched_name).first()
                self.review.append({
                    'tipo': 'Deal — partner por fuzzy', 'nombre': dealname,
                    'detalle': f'"{candidate}" → Colaborador "{matched_name}" (revisar)'
                })
                return ('colaborador', obj)

        self.review.append({
            'tipo': 'Deal — partner no encontrado', 'nombre': dealname,
            'detalle': f'Candidatos probados: {candidates[:3]}'
        })
        return None

    def _resolve_stage_label(self, p):
        """Devuelve la etiqueta legible del dealstage a partir del ID en HubSpot."""
        return self._pipeline_stages.get(p.get('dealstage', ''), '')

    def _upsert_round(self, hs_id, nombre, company, partner, p):
        from crm.models import Round, Introduction, EstadoPresentacion
        company_name = company.name if company else '(dry-run)'
        self.stdout.write(f'  [Ronda]       {nombre} ({company_name})')

        createdate   = self._parse_date(p.get('createdate'))
        closedate    = self._parse_date(p.get('closedate'))
        amount       = self._parse_amount(p.get('amount'))
        stage_label  = self._resolve_stage_label(p)
        crm_ep_name  = HS_STAGE_TO_PRESENTACION.get(stage_label)

        if not self.dry_run:
            ronda, created = Round.objects.get_or_create(
                company=company, type=nombre,
                defaults={'start': createdate, 'close': closedate}
            )
            if created:
                self.stats['rounds'] += 1

            intro_status = None
            if crm_ep_name:
                intro_status = EstadoPresentacion.objects.filter(
                    nombre__iexact=crm_ep_name).first()

            if partner and partner[0] == 'investor' and partner[1]:
                Introduction.objects.get_or_create(
                    round=ronda, investor=partner[1],
                    defaults={
                        'company': company,
                        'status':  intro_status,
                        'ticket':  amount,
                        'date':    createdate,
                    }
                )
            elif partner and partner[0] == 'colaborador' and partner[1]:
                Introduction.objects.get_or_create(
                    round=ronda, colaborador=partner[1],
                    defaults={
                        'company': company,
                        'status':  intro_status,
                        'date':    createdate,
                    }
                )
        else:
            self.stats['rounds'] += 1

    def _upsert_proceso_ma(self, hs_id, nombre, company, partner, p):
        from crm.models import ProcesoMA, ContactoMA, FaseMA
        company_name = company.name if company else '(dry-run)'
        self.stdout.write(f'  [ProcesoMA]   {nombre} ({company_name})')

        createdate  = self._parse_date(p.get('createdate'))
        closedate   = self._parse_date(p.get('closedate'))
        amount      = self._parse_amount(p.get('amount'))
        stage_label = self._resolve_stage_label(p)
        crm_fase    = HS_STAGE_TO_FASE_MA.get(stage_label)
        cerrado     = stage_label in ('Inversión no realizada',)

        if not self.dry_run:
            proc_fase = None
            if crm_fase:
                proc_fase, _ = FaseMA.objects.get_or_create(
                    nombre=crm_fase,
                    defaults={'orden': FaseMA.objects.count()}
                )

            proceso, created = ProcesoMA.objects.get_or_create(
                company=company, nombre=nombre,
                defaults={
                    'fase':          proc_fase,
                    'precio_pedido': amount,
                    'cerrado':       cerrado,
                    'start':         createdate,
                    'close':         closedate,
                    'notes':         p.get('description') or '',
                }
            )
            if created:
                self.stats['procesos_ma'] += 1

            if partner:
                inv   = partner[1] if partner[0] == 'investor'    else None
                colab = partner[1] if partner[0] == 'colaborador' else None
                if inv or colab:
                    ContactoMA.objects.get_or_create(
                        proceso=proceso, investor=inv, comprador=colab,
                        defaults={'date': createdate}
                    )
        else:
            self.stats['procesos_ma'] += 1

    def _upsert_colaboracion(self, hs_id, nombre, company, partner, p):
        from crm.models import Colaboracion, EstadoColaboracion
        company_name = company.name if company else '(dry-run)'
        self.stdout.write(f'  [Colaboracion]{nombre} ({company_name})')

        createdate   = self._parse_date(p.get('createdate'))
        stage_label  = self._resolve_stage_label(p)
        crm_st_name  = HS_STAGE_TO_COLABORACION.get(stage_label)

        if not self.dry_run:
            col_status = None
            if crm_st_name:
                col_status = EstadoColaboracion.objects.filter(
                    nombre__iexact=crm_st_name).first()

            colab_partner = partner[1] if partner and partner[0] == 'colaborador' else None
            inv_partner   = partner[1] if partner and partner[0] == 'investor'    else None

            if colab_partner or inv_partner:
                col, created = Colaboracion.objects.get_or_create(
                    company=company,
                    colaborador=colab_partner,
                    investor=inv_partner,
                    defaults={
                        'descripcion': nombre,
                        'status':      col_status,
                        'date':        createdate,
                        'notes':       p.get('description') or '',
                    }
                )
                if created:
                    self.stats['colaboraciones'] += 1
            else:
                self.review.append({
                    'tipo': 'Colaboración sin colaborador', 'nombre': nombre,
                    'detalle': f'Participada: {company_name}'
                })
        else:
            self.stats['colaboraciones'] += 1

    # ── FASE 4: Actividades ─────────────────────────────────────────────────

    def _import_activities(self):
        self.stdout.write('\n[4/4] Importando actividades (notas, emails, llamadas, reuniones)...')
        total     = 0
        seen_ids  = set()

        eng_configs = [
            ('notes',    ['hs_note_body', 'hs_timestamp', 'hs_createdate']),
            ('calls',    ['hs_call_body', 'hs_call_title', 'hs_timestamp', 'hs_createdate']),
            ('meetings', ['hs_meeting_body', 'hs_meeting_title', 'hs_timestamp', 'hs_createdate']),
        ]

        for eng_type, props_list in eng_configs:
            after = None
            while True:
                try:
                    res = self.client.crm.objects.basic_api.get_page(
                        object_type=eng_type,
                        limit=100, after=after,
                        properties=['hs_object_id'] + props_list,
                        associations=['companies', 'contacts'])
                    for act in res.results:
                        act_id = act.properties.get('hs_object_id', '')
                        if act_id not in seen_ids:
                            seen_ids.add(act_id)
                            self._process_activity(act, eng_type)
                            total += 1
                    if not res.paging or not res.paging.next:
                        break
                    after = res.paging.next.after
                except Exception as e:
                    self.stdout.write(f'  [WARN] {eng_type}: {str(e)[:120]}')
                    break

        self.stdout.write(f'  -> {total} actividades procesadas en HubSpot')

    def _process_activity(self, hs_obj, eng_type):
        p        = hs_obj.properties
        log_type = {'notes': 'Nota', 'calls': 'Llamada',
                    'emails': 'Email', 'meetings': 'Reunión'}.get(eng_type, 'Nota')
        body     = (p.get('hs_note_body') or p.get('hs_call_body') or
                    p.get('hs_email_text') or p.get('hs_meeting_body') or '').strip()
        ts       = p.get('hs_timestamp') or p.get('hs_createdate') or ''
        log_date = self._parse_date(ts) or date.today()

        investor = colaborador = None
        if hs_obj.associations:
            companies_assoc = (hs_obj.associations.get('companies')
                               if hasattr(hs_obj.associations, 'get')
                               else getattr(hs_obj.associations, 'companies', None))
            results = []
            if companies_assoc:
                results = (getattr(companies_assoc, 'results', None)
                           or (companies_assoc.get('results')
                               if hasattr(companies_assoc, 'get') else []) or [])
            for assoc in results:
                hs_id = str(getattr(assoc, 'id', None) or assoc.get('id', ''))
                if hs_id in self.hs_investor_map:
                    investor = self.hs_investor_map[hs_id]
                    break
                if hs_id in self.hs_colab_map:
                    colaborador = self.hs_colab_map[hs_id]
                    break

        if not investor and not colaborador:
            return

        self.stdout.write(f'  [{log_type:8s}] {log_date} → {(investor or colaborador).name[:40]}')

        if not self.dry_run:
            from crm.models import InvestorLog, ColaboradorLog
            hs_act_id = p.get('hs_object_id', '')
            if investor:
                InvestorLog.objects.get_or_create(
                    investor=investor, context=f'hs:{hs_act_id}',
                    defaults={
                        'date': log_date, 'type': log_type,
                        'summary': body[:2000], 'created_by': 'HubSpot import',
                    }
                )
            elif colaborador:
                ColaboradorLog.objects.get_or_create(
                    colaborador=colaborador, context=f'hs:{hs_act_id}',
                    defaults={
                        'date': log_date, 'type': log_type,
                        'summary': body[:2000], 'created_by': 'HubSpot import',
                    }
                )
        self.stats['activities'] += 1

    # ── CSV de revisión ─────────────────────────────────────────────────────

    def _write_review_csv(self):
        if not self.review:
            return
        logs_dir = pathlib.Path(settings.BASE_DIR) / 'logs'
        logs_dir.mkdir(exist_ok=True)
        csv_path = logs_dir / 'hubspot_import_review.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['tipo', 'nombre', 'email', 'detalle'])
            writer.writeheader()
            for row in self.review:
                writer.writerow({k: row.get(k, '') for k in ['tipo', 'nombre', 'email', 'detalle']})
        self.stdout.write(self.style.WARNING(f'\n  CSV de revisión: {csv_path}'))

    # ── Resumen ─────────────────────────────────────────────────────────────

    def _print_summary(self):
        mode = 'DRY-RUN' if self.dry_run else 'IMPORTADO'
        self.stdout.write(self.style.SUCCESS(f'\n=== RESUMEN ({mode}) ==='))
        self.stdout.write(f'  Participadas:   {self.stats["companies"]}')
        self.stdout.write(f'  Inversores:     {self.stats["investors"]}')
        self.stdout.write(f'  Colaboradores:  {self.stats["colaboradores"]}')
        self.stdout.write(f'  Contactos:      {self.stats["contacts"]}')
        self.stdout.write(f'  Rondas:         {self.stats["rounds"]}')
        self.stdout.write(f'  Procesos M&A:   {self.stats["procesos_ma"]}')
        self.stdout.write(f'  Colaboraciones: {self.stats["colaboraciones"]}')
        self.stdout.write(f'  Actividades:    {self.stats["activities"]}')
        self.stdout.write(f'  Para revisar:   {len(self.review)}')
        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                '\n  Esto es un DRY-RUN. Ejecuta con --execute para importar realmente.'
            ))
