"""独立的 Target Profile 1.0 配置契约；不执行筛选、预测或排名。"""

from dataclasses import dataclass, replace
from math import isfinite
import re
from types import MappingProxyType
from typing import Mapping


ROLES = frozenset({"hard_constraint", "objective", "report_only", "disabled"})
MODES = frozenset({"minimize", "maximize", "target", "range"})
MISSING_POLICIES = frozenset({"keep_unknown", "exclude"})
EVIDENCE_REQUIREMENTS = frozenset({
    "measured_only", "measured_or_predicted", "predicted_allowed", "any",
})
SCOPES = frozenset({"molecule", "formulation", "delivery", "experiment"})


class ProfileValidationError(ValueError):
    """规格不符合契约；不得静默忽略字段或修正阈值。"""


def _choice(value, choices, field):
    if not isinstance(value, str) or value not in choices:
        raise ProfileValidationError(f"{field} 必须属于 {sorted(choices)}")


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileValidationError(f"{field} 必须是有限数值，不能是布尔值或字符串")
    try:
        valid = isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ProfileValidationError(f"{field} 必须是有限数值")


def _fields(data, allowed, required, context):
    if not isinstance(data, Mapping):
        raise ProfileValidationError(f"{context} 必须是对象")
    if set(data) - allowed:
        raise ProfileValidationError(f"{context} 包含不允许的字段：{set(data) - allowed}")
    if required - set(data):
        raise ProfileValidationError(f"{context} 缺少字段：{required - set(data)}")


@dataclass(frozen=True)
class Criterion:
    role: str
    scope: str | None = None
    mode: str | None = None
    target: float | None = None
    tolerance: float | None = None
    lower: float | None = None
    upper: float | None = None
    equals: bool | None = None
    unit: str | None = None
    missing_policy: str | None = None
    evidence_requirement: str | None = None

    def __post_init__(self):
        _choice(self.role, ROLES, "role")
        if self.scope is not None:
            _choice(self.scope, SCOPES, "scope")
        if self.unit is not None and (not isinstance(self.unit, str) or not self.unit.strip()):
            raise ProfileValidationError("unit 必须为非空字符串；无量纲可省略")
        if self.role == "disabled":
            if any(getattr(self, key) is not None for key in self.__dataclass_fields__
                   if key not in {"role", "scope"}):
                raise ProfileValidationError("disabled 仅接受 role 和可选 scope")
            return
        if self.missing_policy is None:
            object.__setattr__(self, "missing_policy", "keep_unknown")
        if self.evidence_requirement is None:
            object.__setattr__(self, "evidence_requirement", "any")
        _choice(self.missing_policy, MISSING_POLICIES, "missing_policy")
        _choice(self.evidence_requirement, EVIDENCE_REQUIREMENTS, "evidence_requirement")
        for key in ("target", "tolerance", "lower", "upper"):
            if getattr(self, key) is not None:
                _number(getattr(self, key), key)
        if self.equals is not None and not isinstance(self.equals, bool):
            raise ProfileValidationError("equals 只接受布尔值，不接受候选名称或标签")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ProfileValidationError("lower 不能大于 upper")
        if self.tolerance is not None and self.tolerance < 0:
            raise ProfileValidationError("tolerance 不能为负数")
        if self.role == "report_only":
            if self.missing_policy != "keep_unknown":
                raise ProfileValidationError("report_only 不允许 exclude，不能淘汰候选")
            if any(getattr(self, k) is not None for k in
                   ("mode", "target", "tolerance", "lower", "upper", "equals")):
                raise ProfileValidationError("report_only 不接受目标或约束阈值")
        elif self.role == "objective":
            _choice(self.mode, MODES, "mode")
            if self.equals is not None:
                raise ProfileValidationError("objective 不接受 equals")
            if self.mode == "target":
                if self.target is None or self.tolerance is None:
                    raise ProfileValidationError("target 模式必须提供 target 和 tolerance")
                if self.lower is not None or self.upper is not None:
                    raise ProfileValidationError("target 模式不接受 lower/upper")
            elif self.mode == "range":
                if self.lower is None or self.upper is None:
                    raise ProfileValidationError("range 目标必须提供 lower 和 upper")
                if self.target is not None or self.tolerance is not None:
                    raise ProfileValidationError("range 模式不接受 target/tolerance")
            elif any(getattr(self, k) is not None for k in ("target", "tolerance", "lower", "upper")):
                raise ProfileValidationError("minimize/maximize 不接受目标值或区间")
        else:
            if any(getattr(self, k) is not None for k in ("mode", "target", "tolerance")):
                raise ProfileValidationError("hard_constraint 使用 lower/upper 或 equals")
            bounds = self.lower is not None or self.upper is not None
            if bounds == (self.equals is not None):
                raise ProfileValidationError("hard_constraint 必须且只能提供上下限或布尔 equals")

    @classmethod
    def from_dict(cls, data):
        _fields(data, set(cls.__dataclass_fields__), {"role"}, "criterion")
        if any(value is None for value in data.values()):
            raise ProfileValidationError("可选字段请省略，不能显式填写 null")
        return cls(**dict(data))

    def to_dict(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__
                if getattr(self, key) is not None}


@dataclass(frozen=True)
class TargetProfile:
    name: str
    criteria: Mapping[str, Criterion]
    target_profile_version: str = "1.0"

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ProfileValidationError("name 必须为非空规格名称")
        if self.target_profile_version != "1.0":
            raise ProfileValidationError("仅支持 target_profile_version 1.0")
        if not isinstance(self.criteria, Mapping):
            raise ProfileValidationError("criteria 必须为指标对象；允许空规格用于新建")
        copied = {}
        for key, value in self.criteria.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ProfileValidationError("指标 ID 必须使用小写 snake_case，不是名称/CAS/SMILES")
            if not isinstance(value, Criterion):
                raise ProfileValidationError("criteria 值必须为 Criterion；字典输入请用 from_dict")
            copied[key] = value
        object.__setattr__(self, "criteria", MappingProxyType(copied))

    @classmethod
    def from_dict(cls, data):
        _fields(data, {"name", "target_profile_version", "criteria"},
                {"name", "target_profile_version", "criteria"}, "Target Profile")
        if not isinstance(data["criteria"], Mapping):
            raise ProfileValidationError("criteria 必须为对象")
        return cls(name=data["name"], target_profile_version=data["target_profile_version"],
                   criteria={key: Criterion.from_dict(value) for key, value in data["criteria"].items()})

    def to_dict(self):
        return {"name": self.name, "target_profile_version": self.target_profile_version,
                "criteria": {key: value.to_dict() for key, value in self.criteria.items()}}

    def with_criterion(self, metric_id: str, criterion: Criterion):
        """新增或替换指标，返回经过校验的新规格，不修改原规格。"""
        return replace(self, criteria=dict(self.criteria) | {metric_id: criterion})

    def without_criterion(self, metric_id: str):
        criteria = dict(self.criteria)
        del criteria[metric_id]
        return replace(self, criteria=criteria)

    def renamed(self, name: str):
        return replace(self, name=name)
