"""毒理证据会话、三态条件和可解释匹配。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd


指定 = "指定"
不作为条件 = "不作为条件"
未知 = "未知/暂未填写"
条件状态选项 = (指定, 不作为条件, 未知)

字段标签 = {
    "物种": "物种", "品系": "品系", "性别": "性别", "生命周期阶段": "年龄/生命周期阶段",
    "年龄_天": "年龄（天）", "体重_g": "体重（g）", "基因型": "基因型", "给药途径": "给药途径",
    "给药频率": "给药频率", "暴露时长_天": "暴露时长（天）", "观察时长_天": "观察时长（天）",
    "恢复期_天": "恢复期（天）", "毒性终点": "目标毒性终点", "关注器官或特殊问题": "关注器官/特殊问题",
}
可匹配字段 = tuple(字段标签)


def 默认来源策略(来源预设: str = "本地优先") -> dict[str, Any]:
    """返回可保存的策略；即使选择混合预设也不实际查询公开库。"""
    预设 = {
        "本地优先": {"是否查询公开库": False, "是否优先使用历史数据": True},
        "混合模式": {"是否查询公开库": True, "是否优先使用历史数据": True},
        "公共库优先": {"是否查询公开库": True, "是否优先使用历史数据": True},
    }
    return {
        "来源预设": 来源预设 if 来源预设 in 预设 else "本地优先",
        **预设.get(来源预设, 预设["本地优先"]),
        "是否允许缓存结果": True,
        "是否允许人工补录证据": True,
        "启用公开数据源": [],
    }


def 默认匹配策略() -> dict[str, Any]:
    return {
        "A级字段": ["物种", "品系", "基因型", "性别", "生命周期阶段", "年龄_天", "体重_g", "给药途径", "给药频率", "暴露时长_天", "毒性终点"],
        "B级字段": ["物种", "给药途径", "暴露时长_天", "毒性终点"],
        "C级字段": ["物种", "毒性终点"],
        "年龄容差_天": 14.0,
        "体重容差_g": 5.0,
        "暴露时长容差比例": 0.20,
        "排除基因敲除或转基因": True,
        "无A级显示B级": True,
        "无AB级显示C级": True,
        "允许自动降级": True,
    }


def 默认会话() -> dict[str, Any]:
    return {
        "来源策略": 默认来源策略(),
        "条件": {字段: {"状态": 未知, "值": ""} for 字段 in 可匹配字段},
        "匹配策略": 默认匹配策略(),
        "化合物批次": {},
        "化合物清单": [],
    }


def 规范化会话(会话: Mapping[str, Any] | None) -> dict[str, Any]:
    基础 = 默认会话()
    原始 = dict(会话 or {})
    基础["来源策略"].update(dict(原始.get("来源策略") or {}))
    基础["匹配策略"].update(dict(原始.get("匹配策略") or {}))
    for 字段 in 可匹配字段:
        值 = dict((原始.get("条件") or {}).get(字段) or {})
        状态 = 值.get("状态", 未知)
        基础["条件"][字段] = {"状态": 状态 if 状态 in 条件状态选项 else 未知, "值": 值.get("值", "")}
    基础["化合物批次"] = dict(原始.get("化合物批次") or {})
    基础["化合物清单"] = list(原始.get("化合物清单") or [])
    return 基础


def 公开数据源接口状态(来源策略: Mapping[str, Any]) -> pd.DataFrame:
    已启用 = set(来源策略.get("启用公开数据源") or [])
    return pd.DataFrame([
        {"来源": "PubChem GHS", "是否在当前策略中请求": "是" if "PubChem GHS" in 已启用 else "否",
         "状态": "已启用，运行时查询或读取缓存" if "PubChem GHS" in 已启用 else "未启用",
         "说明": "已实现：查询 GHS 危险提示；仅展示，不参与 A/B/C/D 匹配。"},
        *[
            {"来源": 来源, "是否在当前策略中请求": "否", "状态": "仅保留接口，未启用查询",
             "说明": "尚未接入，不生成或补全任何公开库证据。"}
            for 来源 in ("CompTox / ToxRefDB", "CE", "后续其他来源")
        ],
    ])


def _为空(值: Any) -> bool:
    return 值 is None or (isinstance(值, float) and pd.isna(值)) or str(值).strip() == ""


def _文本相同(目标: Any, 记录: Any) -> bool:
    return str(目标).strip().casefold() == str(记录).strip().casefold()


def _数值(值: Any) -> float | None:
    try:
        return float(值)
    except (TypeError, ValueError):
        return None


@dataclass
class 字段比较:
    字段: str
    结果: str
    说明: str


class 毒理证据匹配引擎:
    """按会话配置逐字段比较，绝不把空值解释为匹配。"""

    def __init__(self, 会话: Mapping[str, Any] | None = None) -> None:
        self.会话 = 规范化会话(会话)
        self.策略 = self.会话["匹配策略"]

    def _比较字段(self, 字段: str, 记录: Mapping[str, Any]) -> 字段比较:
        条件 = self.会话["条件"][字段]
        状态, 目标 = 条件["状态"], 条件.get("值", "")
        标签 = 字段标签[字段]
        if 状态 == 不作为条件:
            return 字段比较(字段, "未限定", f"{标签}不作为本轮条件，未比较")
        if 状态 != 指定 or _为空(目标):
            return 字段比较(字段, "目标未知", f"{标签}目标未知，未比较")
        记录值 = 记录.get(字段, "")
        if _为空(记录值):
            return 字段比较(字段, "记录未报告", f"记录未报告{标签}，不能视为匹配")
        if 字段 == "基因型" and self.策略.get("排除基因敲除或转基因", True):
            文本 = str(记录值).casefold()
            if any(词 in 文本 for 词 in ("敲除", "转基因", "knockout", "transgenic", "ko", "tg")):
                return 字段比较(字段, "不匹配", "记录为基因修饰模型，当前策略排除")
        if 字段 == "年龄_天":
            差值 = (_数值(记录值) or float("inf")) - (_数值(目标) or float("inf"))
            return 字段比较(字段, "匹配" if abs(差值) <= float(self.策略["年龄容差_天"]) else "不匹配", f"年龄差 {abs(差值):g} 天，容差 ±{self.策略['年龄容差_天']:g} 天")
        if 字段 == "体重_g":
            差值 = (_数值(记录值) or float("inf")) - (_数值(目标) or float("inf"))
            return 字段比较(字段, "匹配" if abs(差值) <= float(self.策略["体重容差_g"]) else "不匹配", f"体重差 {abs(差值):g} g，容差 ±{self.策略['体重容差_g']:g} g")
        if 字段 == "暴露时长_天":
            基准, 实际 = _数值(目标), _数值(记录值)
            比例 = abs(实际 - 基准) / 基准 if 基准 and 实际 is not None else float("inf")
            return 字段比较(字段, "匹配" if 比例 <= float(self.策略["暴露时长容差比例"]) else "不匹配", f"暴露时长差 {比例:.0%}，容差 ±{float(self.策略['暴露时长容差比例']):.0%}")
        return 字段比较(字段, "匹配" if _文本相同(目标, 记录值) else "不匹配", f"目标：{目标}；记录：{记录值}")

    def _等级(self, 比较: dict[str, 字段比较]) -> tuple[str, str]:
        已指定 = [字段 for 字段, 条件 in self.会话["条件"].items() if 条件["状态"] == 指定 and not _为空(条件.get("值"))]
        if not 已指定:
            return "数据缺口", "尚无已指定的匹配条件，不能给出可比性等级"
        # 记录未报告不等于匹配。即便 B/C 的最小字段集恰好满足，也应以 D 级
        # 参考呈现，防止较宽松的等级把缺失品系、年龄等信息掩盖掉。
        if any(比较[字段].结果 == "记录未报告" for 字段 in 已指定):
            return "D级参考", "记录存在未报告的已指定字段，不视为严格或可比匹配"
        可尝试等级 = ["A"]
        if self.策略.get("允许自动降级", True) and self.策略.get("无A级显示B级", True):
            可尝试等级.append("B")
        if self.策略.get("允许自动降级", True) and self.策略.get("无AB级显示C级", True):
            可尝试等级.append("C")
        for 等级 in 可尝试等级:
            字段组 = [字段 for 字段 in self.策略.get(f"{等级}级字段", []) if 字段 in 已指定]
            if not 字段组:
                continue
            结果 = [比较[字段].结果 for 字段 in 字段组]
            if all(结果项 == "匹配" for 结果项 in 结果):
                return f"{等级}级", f"{等级}级（基于已填写条件）"
        关键字段 = [字段 for 字段 in ("物种", "给药途径") if 字段 in 已指定]
        if 关键字段 and all(比较[字段].结果 == "匹配" for 字段 in 关键字段):
            return "D级参考", "关键背景相同但未达到 A/B/C 级配置"
        return "不匹配", "已指定条件存在不匹配，未自动把空白或相近记录升级"

    def 匹配(self, 证据: pd.DataFrame, 化合物清单: Iterable[Mapping[str, Any]] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        证据 = 证据.copy() if isinstance(证据, pd.DataFrame) else pd.DataFrame()
        化合物 = list(化合物清单 or self.会话.get("化合物清单") or [])
        if 证据.empty:
            缺口 = pd.DataFrame([{"候选编号": str(项.get("候选编号", "未命名化合物")), "数据缺口": "没有可用于本轮的本地或人工毒理证据", "建议": "补录可追溯的实验记录；公开数据库接口当前仅保留。"} for 项 in 化合物])
            return pd.DataFrame(), 缺口
        结果 = []
        for _, 行 in 证据.iterrows():
            记录 = 行.to_dict()
            比较 = {字段: self._比较字段(字段, 记录) for 字段 in 可匹配字段}
            等级, 摘要 = self._等级(比较)
            结果.append({
                **记录, "匹配等级": 等级, "匹配摘要": 摘要,
                "匹配字段": "；".join(字段标签[字段] for 字段, 项目 in 比较.items() if 项目.结果 == "匹配"),
                "未比较字段": "；".join(字段标签[字段] for 字段, 项目 in 比较.items() if 项目.结果 in {"未限定", "目标未知"}),
                "记录未报告字段": "；".join(字段标签[字段] for 字段, 项目 in 比较.items() if 项目.结果 == "记录未报告"),
                "不匹配字段": "；".join(字段标签[字段] for 字段, 项目 in 比较.items() if 项目.结果 == "不匹配"),
                "逐字段说明": " | ".join(f"{字段标签[字段]}：{项目.说明}" for 字段, 项目 in 比较.items()),
            })
        匹配结果 = pd.DataFrame(结果)
        已有候选 = set(匹配结果.get("候选编号", pd.Series(dtype=str)).astype(str))
        缺口项 = [{"候选编号": str(项.get("候选编号", "未命名化合物")), "数据缺口": "无本地/人工证据", "建议": "补录可追溯的物种、途径、剂量、时长和终点记录。"} for 项 in 化合物 if str(项.get("候选编号", "")) not in 已有候选]
        缺口项.extend({"候选编号": str(行.get("候选编号", "")), "数据缺口": "匹配所需字段未报告", "建议": f"补录：{行['记录未报告字段']}"} for _, 行 in 匹配结果[匹配结果["记录未报告字段"].astype(str).ne("")].iterrows())
        return 匹配结果, pd.DataFrame(缺口项)
