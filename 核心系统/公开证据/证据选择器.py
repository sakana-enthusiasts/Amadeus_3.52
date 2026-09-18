from .条件匹配 import condition_match
from .冲突解析 import find_conflicts
from .数据结构 import ResolvedProperty
from .单位标准化 import normalize_evidence


class EvidenceResolver:
    def resolve(self, request, evidence) -> ResolvedProperty:
        candidates = []
        for original in evidence:
            item = normalize_evidence(original)
            matches, distance = condition_match(item, request)
            if matches and item.qualifier == "=":
                rank = ({"measured": 0, "derived": 1, "predicted": 2, "summary": 3}[item.evidence_type], distance)
                candidates.append((rank, original, item))
        if not candidates:
            return ResolvedProperty(request, "missing", reason="No evidence satisfies the requested form and conditions")
        candidates.sort(key=lambda x: (x[0], x[1].evidence_id))
        best_rank = candidates[0][0]
        best = [x for x in candidates if x[0] == best_rank]
        ids = tuple(x[1].evidence_id for x in candidates)
        # 未指定的条件也不能跨温度、溶剂或化学形式静默选择。
        signatures = {repr(tuple(getattr(x[2], key) for key in
                      ("chemical_form", "observed_structure", "temperature", "pH", "pressure", "solvent", "concentration", "wavelength", "phase")))
                      for x in best}
        conflicts = (("Equally ranked evidence has different conditions or chemical forms",)
                     if len(signatures) > 1 else find_conflicts([x[2] for x in best]))
        if conflicts:
            return ResolvedProperty(request, "conflict", evidence_ids=ids, conflicts=conflicts,
                                    reason="Explicit condition or source selection is required")
        return ResolvedProperty(request, "resolved", selected=best[0][2], evidence_ids=ids)
