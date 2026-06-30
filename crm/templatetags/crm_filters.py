import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def count_items(val):
    """Recursively count items in a list or nested dict of lists."""
    if isinstance(val, list):
        return len(val)
    if isinstance(val, dict):
        return sum(count_items(v) for v in val.values())
    return 0


@register.filter
def split_csv(value):
    """Split a comma-separated string into a list, stripping whitespace."""
    if not value:
        return []
    return [s.strip() for s in value.split(',') if s.strip()]


@register.filter
def attr(obj, field_name):
    """Return getattr(obj, field_name) — allows dynamic field access in templates."""
    return getattr(obj, field_name, False)


@register.filter
def pct_of(value, total):
    """Devuelve el porcentaje de value sobre total, redondeado."""
    try:
        return round(float(value) / float(total) * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def intcomma(value):
    """Formatea un número entero con separador de miles (punto español)."""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return "—"
    formatted = f"{v:,}".replace(",", ".")
    return formatted


@register.filter
def euros(value, decimals=0):
    """Formatea un número con separador de miles '.' y decimales ','."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    decimals = int(decimals)
    formatted = f"{value:,.{decimals}f}"
    # Convertir formato anglosajón (1,234.56) a español (1.234,56)
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


@register.filter
def format_log(text):
    """Aplica negritas y color a las etiquetas de log de email al mostrarlas."""
    if not text:
        return ''
    safe = escape(str(text))
    # (In) / (Out) con color
    safe = safe.replace('(In)',  '<strong style="color:#22c55e">(In)</strong>')
    safe = safe.replace('(Out)', '<strong style="color:#3b82f6">(Out)</strong>')
    # Etiquetas al inicio de línea o tras espacio
    for label in ['De:', 'Para:', 'Asunto:', 'Resumen:']:
        safe = re.sub(rf'(?<![A-Za-z]){re.escape(label)}',
                      f'<strong>{label}</strong>', safe)
    # Saltos de línea
    safe = safe.replace('\n', '<br>')
    return mark_safe(safe)


@register.filter
def get_item(dictionary, key):
    """Accede a un dict por clave desde una template variable: mydict|get_item:key"""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
