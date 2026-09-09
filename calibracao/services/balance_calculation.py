from decimal import Decimal, InvalidOperation, localcontext


ZERO = Decimal("0")
SQRT_12 = Decimal(12).sqrt()
SQRT_3 = Decimal(3).sqrt()
MASS_UNIT_FACTORS_TO_GRAM = {
    "mg": Decimal("0.001"),
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "t": Decimal("1000000"),
}


def decimal_or_none(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def decimal_places_from_resolution(resolution, default=3):
    resolution = decimal_or_none(resolution)
    if resolution in (None, ZERO):
        return default
    return max(0, -abs(resolution).normalize().as_tuple().exponent)


def format_by_resolution(value, resolution, extra_places=0, decimal_comma=True):
    value = decimal_or_none(value)
    if value is None:
        return "—"
    places = decimal_places_from_resolution(resolution) + max(0, int(extra_places or 0))
    rendered = f"{value:.{places}f}"
    return rendered.replace(".", ",") if decimal_comma else rendered


def average(values):
    values = [decimal_or_none(value) for value in values]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values, ZERO) / Decimal(len(values))


def sample_standard_deviation(values):
    values = [decimal_or_none(value) for value in values]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    mean = average(values)
    with localcontext() as context:
        context.prec = 28
        variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values) - 1)
        return variance.sqrt()


def indication_error(indication, reference_mass):
    indication = decimal_or_none(indication)
    reference_mass = decimal_or_none(reference_mass)
    if indication is None or reference_mass is None:
        return None
    return indication - reference_mass


def correction_from_error(error):
    error = decimal_or_none(error)
    return -error if error is not None else None


def standard_uncertainty_from_resolution(resolution):
    resolution = decimal_or_none(resolution)
    if resolution is None:
        return None
    return abs(resolution) / SQRT_12


def standard_uncertainty_from_certificate(expanded_uncertainty, coverage_factor):
    expanded_uncertainty = decimal_or_none(expanded_uncertainty)
    coverage_factor = decimal_or_none(coverage_factor)
    if expanded_uncertainty is None or coverage_factor in (None, ZERO):
        return None
    return abs(expanded_uncertainty / coverage_factor)


def standard_uncertainty_from_rectangular_limit(limit):
    limit = decimal_or_none(limit)
    if limit is None:
        return None
    return abs(limit) / SQRT_3


def eccentricity_standard_uncertainty(maximum_difference, indication, eccentricity_load):
    maximum_difference = decimal_or_none(maximum_difference)
    indication = decimal_or_none(indication)
    eccentricity_load = decimal_or_none(eccentricity_load)
    if None in (maximum_difference, indication, eccentricity_load) or eccentricity_load == ZERO:
        return None
    return abs(maximum_difference) * abs(indication) / (Decimal("2") * SQRT_3 * abs(eccentricity_load))


def root_sum_square(values):
    values = [decimal_or_none(value) for value in values]
    values = [abs(value) for value in values if value is not None]
    if not values:
        return None
    with localcontext() as context:
        context.prec = 28
        return sum((value ** 2 for value in values), ZERO).sqrt()


def select_significant_components(components, maximum_discarded_variance_percent=Decimal("1")):
    """Select components while limiting the cumulative discarded variance.

    All informed components remain in the returned audit dictionaries. A component is
    excluded from the adopted RSS only when the sum of excluded variances remains at
    or below the configured percentage of the complete variance.
    """
    normalized = {
        name: abs(value)
        for name, raw_value in components.items()
        if (value := decimal_or_none(raw_value)) is not None
    }
    if not normalized:
        return {
            "included": {},
            "discarded": {},
            "complete_combined": None,
            "adopted_combined": None,
            "discarded_variance_percent": ZERO,
        }

    total_variance = sum((value ** 2 for value in normalized.values()), ZERO)
    if total_variance == ZERO:
        return {
            "included": {},
            "discarded": normalized,
            "complete_combined": ZERO,
            "adopted_combined": ZERO,
            "discarded_variance_percent": ZERO,
        }

    limit = decimal_or_none(maximum_discarded_variance_percent) or ZERO
    limit = min(max(limit, ZERO), Decimal("100"))
    included = dict(normalized)
    discarded = {}
    discarded_variance = ZERO

    for name, value in sorted(normalized.items(), key=lambda item: item[1]):
        candidate_variance = discarded_variance + value ** 2
        candidate_percent = candidate_variance * Decimal("100") / total_variance
        if candidate_percent <= limit:
            discarded[name] = value
            included.pop(name, None)
            discarded_variance = candidate_variance

    return {
        "included": included,
        "discarded": discarded,
        "complete_combined": root_sum_square(normalized.values()),
        "adopted_combined": root_sum_square(included.values()) or ZERO,
        "discarded_variance_percent": discarded_variance * Decimal("100") / total_variance,
    }


def convert_mass(value, source_unit, target_unit):
    value = decimal_or_none(value)
    source_factor = MASS_UNIT_FACTORS_TO_GRAM.get((source_unit or "").strip().lower())
    target_factor = MASS_UNIT_FACTORS_TO_GRAM.get((target_unit or "").strip().lower())
    if value is None or source_factor is None or target_factor is None:
        return value
    return value * source_factor / target_factor
