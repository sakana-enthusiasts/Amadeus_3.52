"""规格校验、指标绑定与执行预检；不执行模型、查询或候选评价。"""

from dataclasses import dataclass
from math import isfinite

from .数据结构 import Criterion, ProfileValidationError, TargetProfile
from .指标绑定 import METRIC_BINDINGS, MetricBinding


@dataclass(frozen=True)
class PlannedCriterion:
    metric_id: str
    criterion: Criterion
    binding: MetricBinding

    def to_dict(self):
        return {"metric_id": self.metric_id, **self.criterion.to_dict(),
                "binding": self.binding.to_dict()}


@dataclass(frozen=True)
class ExecutionPlan:
    criteria: tuple[PlannedCriterion, ...]
    disabled: tuple[str, ...]

    @property
    def objectives(self):
        return tuple(x for x in self.criteria if x.criterion.role == "objective")

    def to_dict(self):
        return {"criteria": [x.to_dict() for x in self.criteria], "disabled": list(self.disabled),
                "required_metrics": [x.metric_id for x in self.criteria],
                "merge_rule": "hard constraints AND；直接冲突报错；Profile objectives 优先；无则 legacy"}


def compile_profile(profile, *, legacy_constraints=None, available_properties=None,
                    model_selection=None):
    if not isinstance(profile, TargetProfile):
        raise ProfileValidationError("目标规格必须为 TargetProfile")
    profile = TargetProfile.from_dict(profile.to_dict())
    legacy = legacy_constraints or {}
    planned, disabled, checks = [], [], []
    for metric_id, criterion in profile.criteria.items():
        if criterion.role == "disabled":
            disabled.append(metric_id)
            continue
        binding = METRIC_BINDINGS.get(metric_id)
        reasons = []
        if binding is None:
            reasons.append("unsupported：metric_id 未绑定（delivery/experiment 当前无执行能力）")
        else:
            if criterion.scope is not None and criterion.scope != binding.scope:
                reasons.append("scope 与绑定不匹配")
            if not binding.executable:
                reasons.append("unavailable：绑定无执行来源")
            if criterion.role not in binding.roles:
                reasons.append("unsupported：该 scope 尚不支持此 role")
            if criterion.unit is not None and criterion.unit != binding.unit:
                reasons.append(f"unit 不兼容：标准单位 {binding.unit}，当前无正式换算接口")
            if criterion.equals is not None:
                reasons.append("unsupported：当前绑定为数值指标，无法执行布尔 equals")
            if (criterion.evidence_requirement != "any" and
                    not set(binding.evidence_types) & {"measured", "predicted"}):
                reasons.append("当前绑定无法满足该 evidence_requirement")
            if binding.source == "配方物性":
                if available_properties is not None and binding.field not in available_properties:
                    reasons.append("unavailable：当前模型注册表无所需指标")
                if criterion.evidence_requirement == "measured_only":
                    reasons.append("当前绑定无法满足该 evidence_requirement：发现流程没有配方实测输入")
                if (model_selection or {}).get(binding.field) == "measured_only":
                    reasons.append("unavailable：发现流程所选 measured_only 无实测输入")
            if criterion.role == "hard_constraint":
                old = (legacy.get("分子约束", {}).get(binding.field, {}) if binding.scope == "molecule"
                       else legacy.get("物性约束", {}).get(binding.field, {}))
                if metric_id == "cost" and "成本上限_元_kg" in legacy:
                    old = {"最大": legacy["成本上限_元_kg"]}
                try:
                    # legacy 范围契约接受有限数值字符串；不改变该输入语义。
                    bounds = {}
                    for key, value in old.items():
                        if key not in {"最小", "最大"} or isinstance(value, bool):
                            raise ValueError
                        bounds[key] = float(value)
                        if not isfinite(bounds[key]):
                            raise ValueError
                    lowers = [x for x in (criterion.lower, bounds.get("最小")) if x is not None]
                    uppers = [x for x in (criterion.upper, bounds.get("最大")) if x is not None]
                    if lowers and uppers and max(lowers) > min(uppers):
                        reasons.append("legacy 与 Target Profile hard constraints 直接冲突")
                except (TypeError, ValueError, OverflowError):
                    reasons.append("legacy 范围不是合法有限数值约束")
            planned.append(PlannedCriterion(metric_id, criterion, binding))
        checks.append({"metric_id": metric_id, "role": criterion.role,
                       "status": "unsupported/unavailable" if reasons else "ready", "reasons": reasons})
    preflight = {"passed": all(x["status"] == "ready" for x in checks), "criteria": checks}
    return ExecutionPlan(tuple(planned), tuple(disabled)), preflight
