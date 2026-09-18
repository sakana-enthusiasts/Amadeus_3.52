"""保守解析单条物性文字；不把年份、温度或文献编号当成测量值。"""

import re

from 核心系统.公开证据.单位标准化 import convert


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
UNITS = r"g/100\s*mL|mg/mL|g/mL|g/cm³|g/cm3|kg/m3|mg/L|g/L|g/l|mol/L|mmHg|kPa|Pa\s*s|mPa\s*s|Pa|bar|atm|cP|mN/m|N/m|dyn/cm|°C|deg\s*C|°F|K"


def parse_quantity(text, default_unit="", *, dimensionless=False):
    text = text.strip()
    for phrase, symbol in (("greater than or equal to", ">="), ("less than or equal to", "<="),
                           ("greater than", ">"), ("less than", "<")):
        if text.lower().startswith(phrase):
            text = symbol + text[len(phrase):]
            break
    match = re.match(rf"^(?P<qualifier><=|>=|<|>|≤|≥|~|≈)?\s*(?P<first>{NUMBER})"
                     rf"(?:\s*(?:-|–|to)\s*(?P<second>{NUMBER}))?(?:\s*±\s*{NUMBER})?\s*(?P<unit>{UNITS})?(?=\s|$|[,;(±])", text)
    if not match:
        return text, "", "text"
    unit = match.group("unit") or default_unit
    if not unit and not dimensionless:
        return text, "", "text"
    value = float(match.group("first"))
    qualifier = match.group("qualifier") or "="
    if match.group("second"):
        value = {"lower": value, "upper": float(match.group("second"))}
        qualifier = "range"
    return value, unit, qualifier


def parse_conditions(text):
    conditions = {}
    temp = re.search(rf"({NUMBER})\s*(°\s*C|deg\s*C|°\s*F|K)\b", text)
    if temp:
        conditions["temperature"] = convert(float(temp.group(1)), temp.group(2).replace(" ", ""))[0]
    ph = re.search(rf"\bpH\s*[=:]?\s*({NUMBER})", text, re.I)
    if ph:
        conditions["pH"] = float(ph.group(1))
    pressure = re.search(rf"\bat\s+({NUMBER})\s*(kPa|Pa|atm|bar|mmHg)\b", text, re.I)
    if pressure:
        conditions["pressure"] = convert(float(pressure.group(1)), pressure.group(2))[0]
    solvent = re.search(r"\b(?:in|solvent[:=])\s+(water|ethanol|methanol|acetone|benzene)\b", text, re.I)
    if solvent:
        conditions["solvent"] = solvent.group(1).lower()
    uncertainty = re.search(rf"±\s*({NUMBER})", text)
    if uncertainty:
        conditions["uncertainty"] = float(uncertainty.group(1))
    return conditions


def evidence_kind(text):
    if re.search(r"predicted|estimated|calculated|\best\.|\bcalc\.|QSAR|OPERA|TEST model", text, re.I):
        return "predicted"
    if re.search(r"measured|experimental measurement|determined experimentally", text, re.I):
        return "measured"
    return "summary"
