from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import sqrt

PH_FARADAY = Decimal("96485.3399")
PH_GAS_CONSTANT = Decimal("8.314472")
PH_LN10 = Decimal("2.302585092994046")


def _to_decimal(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def average(values):
    numeros = [_to_decimal(valor) for valor in values if _to_decimal(valor) is not None]
    if not numeros:
        return None
    return sum(numeros) / Decimal(len(numeros))


def stdev(values):
    numeros = [_to_decimal(valor) for valor in values if _to_decimal(valor) is not None]
    if len(numeros) <= 1:
        return None
    media = sum(numeros) / Decimal(len(numeros))
    variancia = sum((valor - media) ** 2 for valor in numeros) / Decimal(len(numeros) - 1)
    return variancia.sqrt()


def error(media, referencia):
    media_d = _to_decimal(media)
    referencia_d = _to_decimal(referencia)
    if media_d is None or referencia_d is None:
        return None
    return media_d - referencia_d


def teorico_ph_from_mv(valor_mv, temperatura_c=25):
    mv = _to_decimal(valor_mv)
    temperatura = _to_decimal(temperatura_c)
    if mv is None or temperatura is None:
        return None
    numerador = mv * PH_FARADAY
    denominador = PH_LN10 * PH_GAS_CONSTANT * (Decimal("273.15") + temperatura) * Decimal("1000")
    if denominador == 0:
        return None
    return Decimal("7") - (numerador / denominador)


def slope_teorico_ph(temperatura_c=25):
    temperatura = _to_decimal(temperatura_c)
    if temperatura is None:
        return None
    numerador = PH_LN10 * PH_GAS_CONSTANT * (Decimal("273.15") + temperatura) * Decimal("1000")
    if PH_FARADAY == 0:
        return None
    return numerador / PH_FARADAY


def combination_quadratic(componentes):
    valores = [_to_decimal(valor) for valor in componentes if _to_decimal(valor) is not None]
    if not valores:
        return None
    return sum(valor ** 2 for valor in valores).sqrt()


def fator_abrangencia_95(graus_liberdade):
    if graus_liberdade in (None, ""):
        return Decimal("2")
    try:
        veff = float(graus_liberdade)
    except (TypeError, ValueError):
        return Decimal("2")
    if veff >= 30:
        return Decimal("2")
    if veff >= 20:
        return Decimal("2.09")
    if veff >= 15:
        return Decimal("2.13")
    if veff >= 10:
        return Decimal("2.23")
    if veff >= 9:
        return Decimal("2.26")
    if veff >= 8:
        return Decimal("2.31")
    if veff >= 7:
        return Decimal("2.36")
    if veff >= 6:
        return Decimal("2.45")
    if veff >= 5:
        return Decimal("2.57")
    if veff >= 4:
        return Decimal("2.78")
    if veff >= 3:
        return Decimal("3.18")
    if veff >= 2:
        return Decimal("4.30")
    if veff >= 1:
        return Decimal("12.71")
    return Decimal("2")


def calcular_incerteza(componentes, graus_liberdade=None, fator_k=None):
    uc = combination_quadratic(componentes)
    if uc is None:
        return {
            "incerteza_padrao_combinada": None,
            "incerteza_expandida": None,
            "fator_k": None,
            "graus_liberdade": None,
        }

    if fator_k in (None, ""):
        fator_k = fator_abrangencia_95(graus_liberdade)
    fator_k = _to_decimal(fator_k) or Decimal("2")
    return {
        "incerteza_padrao_combinada": uc,
        "incerteza_expandida": uc * fator_k,
        "fator_k": fator_k,
        "graus_liberdade": _to_decimal(graus_liberdade),
    }
