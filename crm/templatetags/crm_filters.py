from django import template

register = template.Library()


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
