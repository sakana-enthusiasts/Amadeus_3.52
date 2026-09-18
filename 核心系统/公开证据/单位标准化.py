"""只做有明确量纲的转换；不猜测百分比、对数或摩尔浓度的含义。"""

from dataclasses import replace
from numbers import Real

from .数据结构 import PropertyEvidence


UNIT_CONVERSIONS = {
    "mg/L": ("g/L", 0.001, 0), "g/L": ("g/L", 1, 0), "g/l": ("g/L", 1, 0),
    "mg/mL": ("g/L", 1, 0), "g/100 mL": ("g/L", 10, 0),
    "g/cm3": ("kg/m3", 1000, 0), "g/cm³": ("kg/m3", 1000, 0),
    "g/mL": ("kg/m3", 1000, 0), "kg/m3": ("kg/m3", 1, 0),
    "cP": ("Pa s", 0.001, 0), "mPa s": ("Pa s", 0.001, 0), "Pa s": ("Pa s", 1, 0),
    "mmHg": ("Pa", 133.322368, 0), "kPa": ("Pa", 1000, 0), "bar": ("Pa", 100000, 0),
    "atm": ("Pa", 101325, 0), "Pa": ("Pa", 1, 0),
    "°C": ("K", 1, 273.15), "deg C": ("K", 1, 273.15), "C": ("K", 1, 273.15),
    "°F": ("K", 5 / 9, 255.3722222222222), "K": ("K", 1, 0),
    "mN/m": ("N/m", 0.001, 0), "dyn/cm": ("N/m", 0.001, 0), "N/m": ("N/m", 1, 0),
}


def convert(value, unit: str):
    conversion = UNIT_CONVERSIONS.get(unit.strip())
    if conversion is None:
        return value, unit
    canonical, factor, offset = conversion
    if isinstance(value, Real) and not isinstance(value, bool):
        return float(value) * factor + offset, canonical
    if isinstance(value, dict) and set(value) == {"lower", "upper"}:
        return {key: float(v) * factor + offset for key, v in value.items()}, canonical
    return value, unit


def normalize_evidence(evidence: PropertyEvidence) -> PropertyEvidence:
    value, unit = convert(evidence.value, evidence.unit)
    if (value, unit) == (evidence.value, evidence.unit):
        return evidence
    extra = {**evidence.extra, "original_value": evidence.value, "original_unit": evidence.unit}
    uncertainty = evidence.uncertainty
    if isinstance(uncertainty, Real):
        uncertainty = float(uncertainty) * UNIT_CONVERSIONS[evidence.unit.strip()][1]
    return replace(evidence, value=value, unit=unit, uncertainty=uncertainty, extra=extra)
