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


def error(measured, reference):
    measured = as_decimal(measured)
    reference = as_decimal(reference)
    if measured is None or reference is None:
        return None
    return measured - reference


def correction(measurement_error):
    measurement_error = as_decimal(measurement_error)
    return -measurement_error if measurement_error is not None else None


def repeatability_range(values):
    values = [as_decimal(value) for value in values]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    return max(values) - min(values)


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


def resolved_tolerance(reference, criterion_value, criterion_type):
    reference = as_decimal(reference)
    criterion_value = as_decimal(criterion_value)
    if criterion_value is None:
        return None
    if criterion_type == "percentual":
        if reference is None:
            return None
        return abs(reference) * abs(criterion_value) / Decimal("100")
    return abs(criterion_value)


def conformity_result(measurement_error, tolerance, expanded_uncertainty, decision_rule):
    measurement_error = as_decimal(measurement_error)
    tolerance = as_decimal(tolerance)
    expanded_uncertainty = as_decimal(expanded_uncertainty) or Decimal("0")
    if decision_rule == "sem_declaracao" or measurement_error is None or tolerance is None:
        return "nao_declarado"
    decision_value = abs(measurement_error)
    if decision_rule == "banda_guarda":
        decision_value += abs(expanded_uncertainty)
    return "aprovado" if decision_value <= tolerance else "reprovado"
