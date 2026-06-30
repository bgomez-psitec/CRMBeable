import re
from decimal import Decimal

MA_TERMINAL = ('Vendido', 'Descartado')
COLLAB_TERMINAL = ('Activo', 'Descartado')

COLLAB_ESTADO_W = {
    'No contactado':       Decimal('0'),
    'Contactado':          Decimal('0.10'),
    'Reunión inicial':     Decimal('0.25'),
    'Interés confirmado':  Decimal('0.40'),
    'PoC / Piloto':        Decimal('0.60'),
    'Acuerdo firmado':     Decimal('1.0'),
    'Activo':              Decimal('1.0'),
    'Descartado':          Decimal('0'),
}

ESTADO_W = {
    'No contactado': Decimal('0'),
    'Intro realizada': Decimal('0.1'),
    'Reunión inicial': Decimal('0.2'),
    'Interés': Decimal('0.3'),
    'Term sheet': Decimal('0.5'),
    'Due diligence': Decimal('0.8'),
    'Invertido': Decimal('1'),
    'Descartado': Decimal('0'),
}



def round_invertido(round_obj):
    """Suma de tickets de presentaciones en estado Invertido para una ronda."""
    return sum(
        i.ticket or 0
        for i in round_obj.introductions.all()
        if i.status and i.status.nombre == 'Invertido'
    )


def round_weighted(round_obj):
    """Pipeline ponderado: suma de tickets * peso del estado (excluye Invertido)."""
    return sum(
        (i.ticket or 0) * ESTADO_W.get(i.status.nombre if i.status else '', Decimal('0'))
        for i in round_obj.introductions.all()
        if not i.status or i.status.nombre != 'Invertido'
    )


def active_investors_round(round_obj):
    return round_obj.introductions.exclude(status__nombre__in=['Descartado', 'No contactado']).count()


def intro_last_contact(introduction):
    dates = [it.date for it in introduction.interactions.all() if it.date]
    if introduction.date:
        dates.append(introduction.date)
    return max(dates) if dates else None


def company_invertido(company):
    return sum(round_invertido(r) for r in company.rounds.all())


MA_ESTADO_W = {
    'No contactado': Decimal('0'),
    'Identificado': Decimal('0.05'),
    'Contactado': Decimal('0.10'),
    'Reunión mantenida': Decimal('0.20'),
    'NDA firmado': Decimal('0.35'),
    'Due Diligence': Decimal('0.55'),
    'Oferta recibida': Decimal('0.75'),
    'Negociación': Decimal('0.90'),
    'Vendido': Decimal('1'),
    'Descartado': Decimal('0'),
}


def proceso_ma_vendido(proceso):
    return sum(
        c.oferta_precio or 0
        for c in proceso.contactos.all()
        if c.status and c.status.nombre == 'Vendido'
    )


def proceso_ma_weighted(proceso):
    return sum(
        (c.oferta_precio or 0) * MA_ESTADO_W.get(c.status.nombre if c.status else '', Decimal('0'))
        for c in proceso.contactos.all()
        if not c.status or c.status.nombre != 'Vendido'
    )


def active_rounds(company):
    return company.rounds.exclude(status__nombre='Cerrada')
