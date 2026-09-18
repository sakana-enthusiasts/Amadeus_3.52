"""所有模型共享输入和结果契约；模型是策略对象，不调用功能插件。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from math import isclose, isfinite
from typing import Any, Mapping


class 输入不可用(ValueError):
    """数据缺失或不满足模型适用条件，可由 auto 尝试下一个模型。"""


def 有限数(值: Any, 名称: str, *, 最小: float | None = None, 严格正: bool = False) -> float:
    try:
        if isinstance(值, bool):
            raise ValueError
        数 = float(值)
    except (TypeError, ValueError):
        raise 输入不可用(f"{名称}缺失或不是有限数值") from None
    if not isfinite(数) or (严格正 and 数 <= 0) or (最小 is not None and 数 < 最小):
        raise 输入不可用(f"{名称}超出范围")
    return 数


@dataclass(frozen=True)
class 物性结果:
    指标: str
    值: float | None
    单位: str
    状态: str
    方法: str
    模型版本: str = "1.0"
    置信度: float | None = None
    适用范围: str = ""
    警告: tuple[str, ...] = ()
    数据来源: str = ""
    不确定度: float | None = None
    依赖: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.状态 in {"已预测", "已实测"} and self.值 is None:
            raise ValueError("成功结果必须有数值")
        if self.值 is not None:
            有限数(self.值, "结果值")
        if self.置信度 is not None and not 0 <= 有限数(self.置信度, "置信度") <= 1:
            raise ValueError("置信度必须在 0 到 1 之间")
        if self.不确定度 is not None:
            有限数(self.不确定度, "不确定度", 最小=0)

    def 转字典(self) -> dict[str, Any]:
        结果 = asdict(self)
        结果["警告"] = list(self.警告)
        return 结果


@dataclass(frozen=True)
class 配方输入:
    成分: tuple[Mapping[str, Any], ...]
    条件: Mapping[str, Any] = field(default_factory=dict)
    参数: Mapping[str, Any] = field(default_factory=dict)
    配方编号: str = ""

    def 分数(self, 字段: str) -> list[tuple[Mapping[str, Any], float]]:
        if not self.成分:
            raise 输入不可用("配方无成分")
        列表 = [(行, 有限数(行.get(字段), 字段, 最小=0)) for 行 in self.成分]
        if any(分数 > 1 for _, 分数 in 列表) or not isclose(sum(x for _, x in 列表), 1, rel_tol=0, abs_tol=1e-6):
            raise 输入不可用(f"{字段}必须在 0 到 1 之间且总和为 1；不会自动补溶剂或归一化")
        return [(行, x) for 行, x in 列表 if x > 0]

    def 温度K(self) -> float:
        return 有限数(有限数(self.条件.get("温度_C"), "温度_C") + 273.15, "温度_K", 严格正=True)


class 物性模型接口(ABC):
    指标 = ""
    单位 = ""
    方法 = ""
    模型版本 = "1.0"
    适用范围 = ""
    依赖指标: tuple[str, ...] = ()
    自动优先级 = 0

    @abstractmethod
    def 预测(self, 配方: 配方输入, 上游: Mapping[str, 物性结果]) -> 物性结果:
        raise NotImplementedError

    def 结果(self, 值: float, *, 警告: tuple[str, ...] = (), 依赖: Mapping[str, Any] | None = None) -> 物性结果:
        return 物性结果(
            self.指标, 值, self.单位, "已预测", self.方法, self.模型版本,
            适用范围=self.适用范围, 警告=警告 + ("未用配方实验校准；置信度与不确定度尚未量化",),
            数据来源="用户输入物性与模型计算", 依赖=依赖 or {},
        )
