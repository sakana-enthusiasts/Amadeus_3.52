"""只按指标契约选择策略并汇总；用途目标和毒理约束不属于本层。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口
from 设置.配方物性设置 import 默认物性模型, 实测字段
from .配方物性接口 import 配方输入, 物性模型接口, 物性结果, 输入不可用, 有限数


class 模型注册表:
    def __init__(self):
        self._模型: dict[str, dict[str, 物性模型接口]] = {}

    def 注册(self, 模型: 物性模型接口) -> None:
        if not isinstance(模型, 物性模型接口) or not 模型.指标 or not 模型.方法:
            raise ValueError("模型必须实现物性模型接口并声明指标和方法")
        if 模型.方法 in {"auto", "measured_only", "measured"}:
            raise ValueError("方法名为保留名称")
        同指标 = self._模型.setdefault(模型.指标, {})
        if 模型.方法 in 同指标:
            raise ValueError(f"模型重复注册：{模型.指标}/{模型.方法}")
        if 同指标 and next(iter(同指标.values())).单位 != 模型.单位:
            raise ValueError("同一指标必须使用相同的标准单位")
        同指标[模型.方法] = 模型

    def 指标列表(self) -> tuple[str, ...]:
        return tuple(self._模型)

    def 模型列表(self, 指标: str) -> tuple[物性模型接口, ...]:
        return tuple(sorted(self._模型[指标].values(), key=lambda m: (-m.自动优先级, m.方法)))

    def 方法列表(self, 指标: str) -> tuple[str, ...]:
        return ("measured_only", "auto", *(m.方法 for m in self.模型列表(指标)))


def 创建默认模型注册表() -> 模型注册表:
    from .折射率.Lorentz_Lorenz import LorentzLorenz模型
    from .黏度.Grunberg_Nissan import GrunbergNissan模型
    from .黏度.理想对数混合 import 理想对数混合模型
    from .黏度.Cheng_2008 import Cheng甘油水模型
    from .扩散.Stokes_Einstein import StokesEinstein模型
    from .渗透.理想渗透压 import 理想渗透压模型
    from .渗透.非理想活度模型 import 渗透系数修正模型
    from .水活度.水活度模型 import 理想水活度模型, 活度系数水活度模型

    注册表 = 模型注册表()
    for 模型类 in (LorentzLorenz模型, GrunbergNissan模型, 理想对数混合模型, Cheng甘油水模型, StokesEinstein模型,
                   理想渗透压模型, 渗透系数修正模型, 理想水活度模型, 活度系数水活度模型):
        注册表.注册(模型类())
    return 注册表


def _验证值(指标: str, 值: Any) -> float:
    数 = 有限数(值, 指标, 最小=0)
    if 指标 == "混合折射率" and 数 < 1:
        raise 输入不可用("折射率必须不小于 1")
    if 指标 in {"混合黏度", "溶液自由扩散系数"} and 数 <= 0:
        raise 输入不可用(f"{指标}必须大于 0")
    if 指标 == "水活度" and 数 > 1:
        raise 输入不可用("水活度必须在 0 到 1 之间")
    return 数


def _有填写(值: Any) -> bool:
    return 值 is not None and str(值).strip().lower() not in {"", "nan", "none", "<na>"}


def 构建配方输入(上下文: dict[str, Any]) -> 配方输入:
    原始 = 上下文.get("成分")
    成分 = 原始.copy() if isinstance(原始, pd.DataFrame) else pd.DataFrame([] if 原始 is None else 原始)
    # 只有明确比例基准的单位才可转换；其他浓度保留原样供其他模块使用。
    for 字段, 单位集合 in (("体积分数", {"v/v%", "% v/v", "体积百分比"}), ("摩尔分数", {"mol%", "摩尔百分比"})):
        if 字段 not in 成分:
            成分[字段] = None
        for i, 行 in 成分.iterrows():
            if not _有填写(行.get(字段)) and str(行.get("浓度单位", "")).strip() in 单位集合:
                try:
                    成分.at[i, 字段] = 有限数(行.get("浓度值"), "浓度值") / 100
                except 输入不可用:
                    pass  # 模型按指标报告缺失，不阻断其他指标。
    return 配方输入(tuple(成分.to_dict("records")), dict(上下文.get("物性条件") or {}),
                    dict(上下文.get("物性模型参数") or {}), str(上下文.get("配方编号", "")))


class 配方物性汇总插件(基础插件接口):
    插件标识 = "配方物性汇总"

    def __init__(self, 注册表: 模型注册表 | None = None):
        self.注册表 = 注册表 if 注册表 is not None else 创建默认模型注册表()

    def 执行(self, 数据上下文: dict[str, Any]) -> dict[str, dict[str, Any]]:
        配方 = 构建配方输入(数据上下文)
        指标集 = self.注册表.指标列表()
        选择 = {k: 默认物性模型.get(k, "measured_only") for k in 指标集} | dict(数据上下文.get("物性模型选择") or {})
        if 未知 := set(选择) - set(指标集):
            raise ValueError(f"未知物性指标：{sorted(未知)}")
        # 配置拼写错误必须可见，即使存在实测值也不隐式吞掉。
        for 指标 in 指标集:
            if 选择.get(指标, "measured_only") not in self.注册表.方法列表(指标):
                raise ValueError(f"未知模型：{指标}/{选择[指标]}")
        实测 = dict(数据上下文.get("配方设置") or {})
        结果: dict[str, 物性结果] = {}
        正在计算: set[str] = set()

        def 计算(指标: str) -> 物性结果:
            if 指标 in 结果:
                return 结果[指标]
            if 指标 in 正在计算:
                raise ValueError(f"模型依赖成环：{指标}")
            if 指标 not in 指标集:
                raise ValueError(f"未注册的依赖指标：{指标}")
            正在计算.add(指标)
            模型们 = self.注册表.模型列表(指标)
            单位 = 模型们[0].单位
            方法 = 选择.get(指标, "measured_only")
            警告: list[str] = []
            测量值 = 实测.get(实测字段.get(指标, ""))
            if _有填写(测量值):
                try:
                    值 = _验证值(指标, 测量值)
                    结果[指标] = 物性结果(指标, 值, 单位, "已实测", "measured", 数据来源=str(实测.get("物性实测来源") or "用户录入"),
                                        适用范围="当前配方及对应实验条件", 警告=("测量不确定度未提供",))
                except 输入不可用 as 错误:
                    结果[指标] = 物性结果(指标, None, 单位, "输入无效", "measured", 警告=(str(错误),))
            elif 方法 == "measured_only":
                结果[指标] = 物性结果(指标, None, 单位, "待补实测", 方法)
            else:
                待尝试 = 模型们 if 方法 == "auto" else tuple(m for m in 模型们 if m.方法 == 方法)
                for 模型 in 待尝试:
                    上游 = {依赖: 计算(依赖) for 依赖 in 模型.依赖指标}
                    try:
                        输出 = 模型.预测(配方, 上游)
                        if (输出.指标, 输出.单位, 输出.方法, 输出.模型版本) != (指标, 单位, 模型.方法, 模型.模型版本):
                            raise ValueError("模型输出的指标、单位、方法或版本不符合注册契约")
                        if 输出.状态 != "已预测":
                            raise 输入不可用("；".join(输出.警告) or 输出.状态)
                        _验证值(指标, 输出.值)
                        结果[指标] = replace(输出, 警告=tuple(警告) + tuple(输出.警告))
                        break
                    except (输入不可用, ArithmeticError) as 错误:
                        警告.append(f"{模型.方法} 不可用：{错误}")
                else:
                    结果[指标] = 物性结果(指标, None, 单位, "无法预测", 方法, 警告=tuple(警告))
            正在计算.remove(指标)
            return 结果[指标]

        return {指标: 计算(指标).转字典() | {"配方编号": 配方.配方编号, "请求方法": 选择.get(指标, "measured_only"),
                                         "条件": dict(配方.条件), "模型参数": dict(配方.参数)} for 指标 in 指标集}
