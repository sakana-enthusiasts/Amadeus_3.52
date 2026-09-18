from .数据结构 import EvidenceRequest, PropertyEvidence


def condition_match(evidence: PropertyEvidence, request: EvidenceRequest) -> tuple[bool, float]:
    if evidence.compound_id != request.compound_id or evidence.property_id != request.property_id:
        return False, float("inf")
    if request.measured_only and evidence.evidence_type != "measured":
        return False, float("inf")
    if request.sources and evidence.source not in request.sources:
        return False, float("inf")
    score = 0.0
    for field in ("chemical_form", "observed_structure", "temperature", "pH", "pressure", "solvent", "concentration", "wavelength", "phase"):
        wanted, actual = getattr(request, field), getattr(evidence, field)
        if wanted is None:
            continue
        if actual is None or actual == "" or actual == "unspecified":
            if not request.allow_unknown_conditions:
                return False, float("inf")
            score += 100
        elif field in {"temperature", "pH", "pressure"}:
            tolerance = getattr(request, f"{field}_tolerance")
            if tolerance < 0:
                raise ValueError("Condition tolerance cannot be negative")
            distance = abs(actual - wanted)
            if distance > tolerance:
                return False, float("inf")
            score += distance / (tolerance or 1)
        elif actual != wanted:
            return False, float("inf")
    return True, score
