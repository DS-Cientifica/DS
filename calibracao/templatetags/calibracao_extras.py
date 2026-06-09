from django import template


register = template.Library()


@register.filter
def decimal_br(valor, casas=4):
    if valor in (None, ""):
        return "—"

    try:
        casas = int(casas)
    except (TypeError, ValueError):
        casas = 4

    return f"{valor:.{casas}f}".replace(".", ",")
