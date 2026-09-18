"""条件属于证据本身。温度统一为 K，压力为 Pa；未知条件保持 None。"""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CompoundIdentity:
    compound_id: str
    chemical_form: str = "unspecified"
    observed_structure: str = ""
    standardized_parent_structure: str = ""
    inchikey: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)
    standardization_version: str = ""


@dataclass(frozen=True)
class PropertyEvidence:
    compound_id: str
    chemical_form: str
    property_id: str
    value: Any
    unit: str = ""
    qualifier: str = "="
    temperature: float | None = None
    pH: float | None = None
    pressure: float | None = None
    solvent: str | None = None
    concentration: Any = None
    wavelength: Any = None
    phase: str | None = None
    evidence_type: str = "summary"
    method: str = ""
    model_name: str = ""
    model_version: str = ""
    uncertainty: Any = None
    applicability_domain: Any = None
    confidence: float | None = None
    source: str = ""
    source_record_id: str = ""
    reference: Any = None
    retrieved_at: str = ""
    parser_version: str = ""
    raw_record_id: str = ""
    observed_structure: str = ""
    standardized_parent_structure: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.evidence_type not in {"measured", "predicted", "derived", "summary"}:
            raise ValueError("Unknown evidence_type")
        if not self.compound_id or not self.property_id or not self.source:
            raise ValueError("Evidence requires compound_id, property_id and source")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")

    @property
    def evidence_id(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class EvidenceRequest:
    compound_id: str
    property_id: str
    chemical_form: str | None = None
    observed_structure: str | None = None
    temperature: float | None = None
    temperature_tolerance: float = 5.0
    pH: float | None = None
    pH_tolerance: float = 0.5
    pressure: float | None = None
    pressure_tolerance: float = 100.0
    solvent: str | None = None
    concentration: Any = None
    wavelength: Any = None
    phase: str | None = None
    measured_only: bool = False
    sources: tuple[str, ...] = ()
    allow_unknown_conditions: bool = False


@dataclass(frozen=True)
class ResolvedProperty:
    request: EvidenceRequest
    status: str
    selected: PropertyEvidence | None = None
    evidence_ids: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class ProviderResult:
    status: str
    evidence: tuple[PropertyEvidence, ...] = ()
    identity: CompoundIdentity | None = None
    message: str = ""
    raw_record_ids: tuple[str, ...] = ()
    cache_hit: bool = False
