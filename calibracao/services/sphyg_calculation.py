from decimal import Decimal, InvalidOperation


SQRT_3 = Decimal(3).sqrt()
SQRT_12 = Decimal(12).sqrt()


def as_decimal(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def average(values):
    values = [as_decimal(value) for value in values]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def sample_standard_deviation(values):
    values = [as_decimal(value) for value in values]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    mean = average(values)
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values) - 1)
    return variance.sqrt()


def measurement_error(indication, reference):
    indication = as_decimal(indication)
    reference = as_decimal(reference)
    if indication is None or reference is None:
        return None
    return indication - reference


def correction_from_error(error):
    error = as_decimal(error)
    return -error if error is not None else None


def hysteresis(increasing_indication, decreasing_indication):
    increasing_indication = as_decimal(increasing_indication)
    decreasing_indication = as_decimal(decreasing_indication)
    if increasing_indication is None or decreasing_indication is None:
        return None
    return abs(increasing_indication - decreasing_indication)


def standard_uncertainty_from_resolution(resolution):
    resolution = as_decimal(resolution)
    return abs(resolution) / SQRT_12 if resolution is not None else None


def standard_uncertainty_from_expanded(expanded_uncertainty, coverage_factor):
    expanded_uncertainty = as_decimal(expanded_uncertainty)
    coverage_factor = as_decimal(coverage_factor) or Decimal("2")
    if expanded_uncertainty is None or coverage_factor == 0:
        return None
    return abs(expanded_uncertainty) / abs(coverage_factor)


def standard_uncertainty_from_repeatability(std_deviation, repetitions):
    std_deviation = as_decimal(std_deviation)
    if std_deviation is None or not repetitions:
        return None
    return abs(std_deviation) / Decimal(repetitions).sqrt()


def standard_uncertainty_from_rectangular_limit(limit):
    limit = as_decimal(limit)
    return abs(limit) / SQRT_3 if limit is not None else None


def root_sum_squares(values):
    values = [as_decimal(value) for value in values]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum((value ** 2 for value in values), Decimal("0")).sqrt()


def leakage_rate(initial_pressure, final_pressure, duration_minutes):
    initial_pressure = as_decimal(initial_pressure)
    final_pressure = as_decimal(final_pressure)
    duration_minutes = as_decimal(duration_minutes)
    if initial_pressure is None or final_pressure is None or not duration_minutes:
        return None
    return abs(initial_pressure - final_pressure) / abs(duration_minutes)


def conformity_result(errors, tolerance, expanded_uncertainty, decision_rule):
    errors = [as_decimal(value) for value in errors]
    errors = [value for value in errors if value is not None]
    tolerance = as_decimal(tolerance)
    expanded_uncertainty = as_decimal(expanded_uncertainty) or Decimal("0")
    if decision_rule == "sem_declaracao" or not errors or tolerance is None:
        return "nao_declarado"
    decision_value = max(abs(value) for value in errors)
    if decision_rule == "banda_guarda":
        decision_value += abs(expanded_uncertainty)
    return "aprovado" if decision_value <= abs(tolerance) else "reprovado"
