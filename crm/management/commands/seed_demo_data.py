from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role, User
from crm.models import (
    Company,
    EstadoPresentacion,
    EtapaRelacion,
    FaseRonda,
    InboxMessage,
    Introduction,
    Investor,
    InvestorContact,
    Round,
)

ESTADOS = ['No contactado', 'Intro realizada', 'Reunión inicial', 'Interés', 'Term sheet',
           'Due diligence', 'Invertido', 'Descartado']
ROUND_PHASES = ['Preparación', 'Listado de Inversores', 'Contactados los inversores', 'Reuniones',
                'Firma de LOIs', 'DD', 'Cierre', 'Cerrada']
RELATION_STAGES = ['Lead', 'Conocido', 'Inversor no Activo', 'Relación activa',
                    'Coinversor no habitual', 'Coinversor habitual', 'Inversor estratégico']

COMPANIES = [
    {'name': 'Lumio Robotics', 'sectors': 'Robótica industrial', 'country': 'España', 'stage': 'Venture Capital',
     'valuation': 18000000,
     'rounds': [
         {'type': 'Seed 2024', 'target': 1500000, 'start': '2024-02-01', 'close': '2024-06-30', 'status': 'Cerrada'},
         {'type': 'Serie A 2026', 'target': 6000000, 'start': '2026-01-15', 'close': '2026-09-30', 'status': 'Reuniones'},
     ]},
    {'name': 'Velora Health', 'sectors': 'Salud digital', 'country': 'España', 'stage': 'Seed', 'valuation': 9000000,
     'rounds': [
         {'type': 'Seed 2026', 'target': 2500000, 'start': '2026-02-01', 'close': '2026-07-15', 'status': 'Firma de LOIs'},
     ]},
    {'name': 'Nervia AI', 'sectors': 'IA / Datos', 'country': 'Portugal', 'stage': 'Venture Capital', 'valuation': 30000000,
     'rounds': [
         {'type': 'Serie B 2026', 'target': 12000000, 'start': '2026-01-10', 'close': '2026-11-30', 'status': 'DD'},
     ]},
    {'name': 'Kairos Energy', 'sectors': 'Energía, Cleantech', 'country': 'España', 'stage': 'Venture Capital', 'valuation': 14000000,
     'rounds': [
         {'type': 'Serie A 2026', 'target': 5000000, 'start': '2026-03-01', 'close': '2026-10-31', 'status': 'Listado de Inversores'},
     ]},
]

INVESTORS = [
    {'name': 'ABaC Nest Ventures', 'type': 'Venture Capital', 'country': 'España', 'sectors': 'Deep tech, Robótica, IA',
     'relation': 'Coinversor habitual', 'notes': 'Coinvierte con nosotros desde 2022. Foco hardware y deep tech.',
     'contacts': [{'name': 'Laura Méndez', 'role': 'Partner', 'email': 'l.mendez@abac.vc', 'phone': '+34 91 555 0101'}]},
    {'name': 'Kfund', 'type': 'Venture Capital', 'country': 'España', 'sectors': 'Software, IA, SaaS',
     'relation': 'Inversor estratégico', 'notes': 'Relación muy estrecha, lead frecuente en Serie A.',
     'contacts': [{'name': 'Pablo Ortega', 'role': 'Principal', 'email': 'pablo@kfund.co', 'phone': '+34 91 555 0144'}]},
    {'name': 'Seaya Ventures', 'type': 'Venture Capital', 'country': 'España', 'sectors': 'Salud, Sostenibilidad',
     'relation': 'Relación activa', 'notes': 'Mandato de impacto y salud digital.',
     'contacts': [{'name': 'Marta Coll', 'role': 'Investment Manager', 'email': 'm.coll@seaya.vc', 'phone': '+34 91 555 0177'}]},
    {'name': 'Mundi Ventures', 'type': 'Venture Capital', 'country': 'España', 'sectors': 'Insurtech, IA, Deep tech',
     'relation': 'Relación activa', 'notes': '',
     'contacts': [{'name': 'Sergio Pérez', 'role': 'Partner', 'email': 'sergio@mundi.vc', 'phone': '+34 91 555 0188'}]},
    {'name': 'Family Office Soler', 'type': 'Family Office', 'country': 'España', 'sectors': 'Diversificado',
     'relation': 'Conocido', 'notes': 'Tickets de coinversión en seed.',
     'contacts': [{'name': 'Andreu Soler', 'role': 'Director de inversiones', 'email': 'a.soler@fosoler.com', 'phone': '+34 93 555 0200'}]},
    {'name': 'Iberdrola Ventures', 'type': 'Corporate Venture Capital', 'country': 'España', 'sectors': 'Energía, Cleantech',
     'relation': 'Relación activa', 'notes': 'CVC estratégico para cleantech.',
     'contacts': [{'name': 'Cristina Vega', 'role': 'Head of Ventures', 'email': 'c.vega@iberdrola.com', 'phone': '+34 91 555 0233'}]},
    {'name': 'Carlos Tusquets', 'type': 'Business Angel', 'country': 'España', 'sectors': 'Salud, Fintech',
     'relation': 'Lead', 'notes': 'Presentado en evento del IESE.',
     'contacts': [{'name': 'Carlos Tusquets', 'role': 'Angel', 'email': 'carlos@tusquets.io', 'phone': '+34 60 555 0266'}]},
    {'name': 'BlueCrow Capital', 'type': 'Family Office', 'country': 'Portugal', 'sectors': 'Energía, Real assets',
     'relation': 'Conocido', 'notes': '',
     'contacts': [{'name': 'João Pinto', 'role': 'Partner', 'email': 'j.pinto@bluecrow.pt', 'phone': '+351 21 555 0300'}]},
]

# (company_index, round_index_in_company, investor_index, date, intro_by, status, ticket, next_action, next_date, notes)
INTRODUCTIONS = [
    (0, 1, 0, '2026-02-10', 'Laura Méndez', 'Interés', 1000000, 'Enviar data room', '2026-06-20', 'Muy interesados en la tracción industrial.'),
    (0, 1, 1, '2026-02-18', 'Equipo VentureOS', 'Reunión inicial', 750000, 'Segunda reunión con CTO', '2026-06-25', ''),
    (0, 1, 5, '', '', 'No contactado', 0, 'Preparar intro', '', 'Posible encaje cleantech-robótica.'),
    (0, 1, 2, '2026-02-05', 'Marta Coll', 'Descartado', 0, '', '', 'Fuera de tesis (foco salud).'),
    (1, 0, 2, '2026-03-01', 'Marta Coll', 'Due diligence', 1000000, 'Revisión clínica', '2026-06-18', 'DD técnica en curso.'),
    (1, 0, 4, '2026-03-10', 'Andreu Soler', 'Intro realizada', 300000, 'Agendar primera llamada', '2026-06-22', ''),
    (1, 0, 6, '2026-03-12', 'Equipo VentureOS', 'Interés', 100000, 'Enviar deck', '2026-06-19', ''),
    (2, 0, 1, '2026-01-20', 'Pablo Ortega', 'Term sheet', 3000000, 'Negociar términos', '2026-06-21', 'Term sheet recibido, en negociación.'),
    (2, 0, 3, '2026-01-15', 'Sergio Pérez', 'Invertido', 4000000, '', '', 'Lead de la ronda, capital comprometido.'),
    (2, 0, 0, '2026-02-01', 'Laura Méndez', 'Interés', 1500000, 'Reunión de seguimiento', '2026-06-24', ''),
    (3, 0, 5, '2026-03-15', 'Cristina Vega', 'Reunión inicial', 1000000, 'Visita a planta piloto', '2026-06-26', ''),
    (3, 0, 7, '', '', 'No contactado', 0, 'Preparar intro', '', ''),
    (3, 0, 0, '2026-03-20', 'Laura Méndez', 'Intro realizada', 500000, 'Enviar one-pager', '2026-06-23', ''),
]

USERS = [
    {'username': 'admin', 'name': 'Admin Principal', 'email': 'admin@ventureos.vc', 'role': Role.ADMIN, 'mfa': True, 'companies': [], 'company': None},
    {'username': 'elena', 'name': 'Elena Torres', 'email': 'elena@ventureos.vc', 'role': Role.EMPLEADO, 'mfa': True, 'companies': [0, 1, 3], 'company': None},
    {'username': 'david', 'name': 'David Ferrer', 'email': 'david@ventureos.vc', 'role': Role.EMPLEADO, 'mfa': False, 'companies': [2], 'company': None},
    {'username': 'marta', 'name': 'Marta Ibáñez', 'email': 'marta@lumio.io', 'role': Role.CEO, 'mfa': True, 'companies': [], 'company': 0},
    {'username': 'alvaro', 'name': 'Álvaro Ruiz', 'email': 'alvaro@velora.health', 'role': Role.CEO, 'mfa': True, 'companies': [], 'company': 1},
]

INBOX = [
    {'from_name': 'Pablo Ortega · Kfund', 'from_email': 'pablo@kfund.co', 'subject': 'Term sheet Nervia AI — comentarios',
     'date': '2026-06-17', 'unread': True,
     'body': 'Hola, hemos revisado el term sheet de Nervia AI y estamos listos para avanzar. Confirmamos el ticket de 3M€ liderando la ronda. Necesitamos cerrar la cláusula de liquidación preferente y agendar una llamada con el CFO esta semana. Adjuntamos nuestra propuesta de valoración.'},
    {'from_name': 'Marta Coll · Seaya', 'from_email': 'marta@seaya.vc', 'subject': 'Documentación DD Velora Health',
     'date': '2026-06-16', 'unread': True,
     'body': 'Buenos días, seguimos avanzando en la due diligence de Velora Health. Nos faltan las métricas de retención de cohortes y el detalle del pipeline regulatorio. Si nos lo enviáis antes del viernes podríamos llevar la inversión a comité la próxima semana.'},
    {'from_name': 'Laura Méndez · ABaC', 'from_email': 'laura@abaccapital.com', 'subject': 'Re: Data room Lumio Serie A',
     'date': '2026-06-16', 'unread': True,
     'body': 'Gracias por el acceso al data room de Lumio. El equipo nos ha parecido muy sólido y la tracción industrial es interesante. Queremos profundizar en los márgenes unitarios; proponemos una reunión la semana que viene para revisar el modelo financiero.'},
    {'from_name': 'Cristina Vega · Iberdrola', 'from_email': 'cristina.vega@iberdrola.com', 'subject': 'Visita planta piloto Kairos',
     'date': '2026-06-12', 'unread': False,
     'body': 'Hola, tras la visita a la planta piloto de Kairos Energy quedamos muy satisfechos. Internamente vemos encaje estratégico con nuestra unidad de renovables. Necesitamos aprobación del comité corporativo antes de comprometer un ticket.'},
    {'from_name': 'Andreu Soler · FO Soler', 'from_email': 'andreu@fosoler.com', 'subject': 'Interés en seed Velora Health',
     'date': '2026-06-10', 'unread': False,
     'body': 'Estimados, nos interesa entrar en la ronda seed de Velora Health con un ticket pequeño de 200k€. Somos un family office y solemos coinvertir con fondos de salud. Quedamos a la espera del deck y los términos de la ronda.'},
]


def _date_or_none(s):
    return s or None


class Command(BaseCommand):
    help = 'Carga datos de demo equivalentes al prototipo CRM_Gestora_ES_V1.html'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Borrando datos previos...')
        InboxMessage.objects.all().delete()
        Introduction.objects.all().delete()
        Round.objects.all().delete()
        InvestorContact.objects.all().delete()
        Investor.objects.all().delete()
        Company.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        EstadoPresentacion.objects.all().delete()
        FaseRonda.objects.all().delete()
        EtapaRelacion.objects.all().delete()

        estados = {nombre: EstadoPresentacion.objects.create(nombre=nombre, orden=i) for i, nombre in enumerate(ESTADOS)}
        fases = {nombre: FaseRonda.objects.create(nombre=nombre, orden=i) for i, nombre in enumerate(ROUND_PHASES)}
        relaciones = {nombre: EtapaRelacion.objects.create(nombre=nombre, orden=i) for i, nombre in enumerate(RELATION_STAGES)}

        companies = []
        for c in COMPANIES:
            company = Company.objects.create(
                name=c['name'], sectors=c['sectors'], country=c['country'],
                stage=c['stage'], valuation=c['valuation'],
            )
            rounds = []
            for r in c['rounds']:
                rounds.append(Round.objects.create(
                    company=company, type=r['type'], target=r['target'],
                    start=r['start'], close=r['close'], status=fases[r['status']],
                ))
            companies.append({'obj': company, 'rounds': rounds})
        self.stdout.write(f'{len(companies)} participadas creadas.')

        investors = []
        for inv in INVESTORS:
            investor = Investor.objects.create(
                name=inv['name'], type=inv['type'], country=inv['country'],
                sectors=inv['sectors'], relation=relaciones[inv['relation']], notes=inv['notes'],
            )
            for contact in inv['contacts']:
                InvestorContact.objects.create(investor=investor, **contact)
            investors.append(investor)
        self.stdout.write(f'{len(investors)} inversores creados.')

        for (ci, ri, ii, date, intro_by, status, ticket, next_action, next_date, notes) in INTRODUCTIONS:
            Introduction.objects.create(
                company=companies[ci]['obj'], round=companies[ci]['rounds'][ri], investor=investors[ii],
                status=estados[status], ticket=ticket, date=_date_or_none(date), intro_by=intro_by,
                next_action=next_action, next_date=_date_or_none(next_date), notes=notes,
            )
        self.stdout.write(f'{len(INTRODUCTIONS)} presentaciones creadas.')

        for u in USERS:
            user = User.objects.create_user(
                username=u['username'], email=u['email'], password='demo1234',
                first_name=u['name'].split(' ')[0], last_name=' '.join(u['name'].split(' ')[1:]),
                role=u['role'], mfa_enabled=u['mfa'],
                company=companies[u['company']]['obj'] if u['company'] is not None else None,
            )
            if u['companies']:
                user.assigned_companies.set([companies[i]['obj'] for i in u['companies']])
        self.stdout.write(f'{len(USERS)} usuarios creados (password demo1234).')

        for msg in INBOX:
            InboxMessage.objects.create(
                from_name=msg['from_name'], from_email=msg['from_email'], subject=msg['subject'],
                body=msg['body'], date=msg['date'], unread=msg['unread'],
            )
        self.stdout.write(f'{len(INBOX)} mensajes de bandeja creados.')

        self.stdout.write(self.style.SUCCESS('Datos de demo cargados correctamente.'))
