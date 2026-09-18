"""冲突保留并阻止自动采用，不对来源值求平均。"""

from numbers import Real


def find_conflicts(evidence, relative_tolerance=0.1, absolute_tolerance=1e-9):
    if len(evidence) < 2:
        return ()
    first = evidence[0]
    conflicts = []
    for item in evidence[1:]:
        if item.unit != first.unit:
            conflicts.append(f"incompatible units: {first.evidence_id}, {item.evidence_id}")
        elif isinstance(first.value, Real) and isinstance(item.value, Real):
            tolerance = max(absolute_tolerance, relative_tolerance * max(abs(first.value), abs(item.value)))
            if abs(first.value - item.value) > tolerance:
                conflicts.append(f"different values: {first.evidence_id}, {item.evidence_id}")
        elif item.value != first.value:
            conflicts.append(f"different values: {first.evidence_id}, {item.evidence_id}")
    return tuple(conflicts)
