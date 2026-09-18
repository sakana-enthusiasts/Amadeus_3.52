"""颅骨透明化的用途级插件。

这里只处理用途目标、证据缺口和上游统一物性结果；具体模型由配方物性层选择。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口
from 插件.配方物性.配方物性接口 import 有限数


用途标识 = "skull_clearing"
用途名称 = "颅骨透明化"
用途配置版本 = "1.0"
成分角色选项 = ("RI匹配液", "共溶剂", "脱钙剂", "脱脂剂", "胶原处理剂", "HSP参照物", "其他", "未指定")
实验终点字段 = ("透射率", "散射系数", "约化散射系数", "吸收系数", "SNR", "PSF_FWHM", "最大成像深度")


def 默认用途配置() -> dict[str, Any]:
    return {
        "用途标识": 用途标识,
        "用途名称": 用途名称,
        "用途配置版本": 用途配置版本,
        "目标折射率": 1.56,
        "温度_C": 25.0,
        "HSP参照体系": "AqIS；oRIMS",
        "物性约束": {},
    }


def _数值(值: Any) -> float | None:
    数值 = pd.to_numeric(pd.Series([值]), errors="coerce").iloc[0]
    return None if pd.isna(数值) else float(数值)


def _表格(值: Any) -> pd.DataFrame:
    return 值.copy() if isinstance(值, pd.DataFrame) else pd.DataFrame([] if 值 is None else 值)


class 颅骨透明化用途配置插件(基础插件接口):
    插件标识 = "颅骨透明化用途配置"

    def 执行(self, 数据上下文: dict[str, Any]) -> dict[str, Any]:
        配置 = 默认用途配置() | dict(数据上下文.get("用途配置") or {})
        if 配置.get("用途标识") != 用途标识:
            raise ValueError("颅骨透明化用途插件只能处理用途标识 skull_clearing")
        目标RI = _数值(配置.get("目标折射率"))
        if 目标RI is None or not 1.0 < 目标RI < 2.0:
            raise ValueError("目标折射率必须是 1.0 至 2.0 之间的数值")
        配置["目标折射率"] = 目标RI
        温度 = _数值(配置.get("温度_C"))
        配置["温度_C"] = 25.0 if 温度 is None else 温度
        配置["HSP参照体系"] = str(配置.get("HSP参照体系") or "").strip()
        return 配置


class 颅骨透明化成分评估插件(基础插件接口):
    插件标识 = "颅骨透明化成分评估"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        成分 = _表格(数据上下文.get("成分"))
        if 成分.empty:
            return pd.DataFrame()
        for 列, 默认值 in {
            "成分键": "", "候选编号": "", "化学名称": "", "颅骨透明化角色": "未指定", "浓度值": pd.NA,
            "浓度单位": "", "纯物质RI": pd.NA, "浓度下RI": pd.NA, "实验水合评分": pd.NA,
            "预测混溶性": "", "实验混溶性": "", "沉淀": "", "浑浊": "", "分层": "",
            "颜色": "", "颜色变化": "", "吸收峰_nm": pd.NA, "pH": pd.NA,
            "脱钙证据": "", "脱脂证据": "", "胶原处理证据": "", "数据来源": "",
        }.items():
            if 列 not in 成分:
                成分[列] = 默认值
        成分["浓度值"] = pd.to_numeric(成分["浓度值"], errors="coerce")
        RI结果 = _表格(数据上下文["成分RI结果"]).set_index("成分键")
        水合结果 = _表格(数据上下文["成分水合结果"]).set_index("成分键")
        成分 = 成分.set_index("成分键")
        for 字段 in ("纯物质RI", "浓度下RI", "RI数据状态", "RI与目标差值"):
            成分[字段] = RI结果[字段]
        for 字段 in ("实验水合评分", "水合数据状态"):
            成分[字段] = 水合结果[字段]
        成分 = 成分.reset_index()
        成分["浓度状态"] = 成分.apply(lambda 行: "已填写" if pd.notna(行["浓度值"]) and 行["浓度值"] > 0 and str(行["浓度单位"]).strip() else "待补浓度", axis=1)
        成分["角色状态"] = 成分["颅骨透明化角色"].astype(str).map(lambda 值: "待指定" if 值 in {"", "未指定", "nan"} else "已指定")
        成分["水合数据状态"] = 成分["实验水合评分"].map(lambda 值: "已有实验水合评分" if pd.notna(值) else "待补实验水合评分")
        成分["相行为状态"] = 成分.apply(lambda 行: "已有实验混溶性" if str(行["实验混溶性"]).strip() else ("已有预测混溶性，待实验验证" if str(行["预测混溶性"]).strip() else "待评估"), axis=1)
        return 成分


class 颅骨透明化配方评估插件(基础插件接口):
    插件标识 = "颅骨透明化配方评估"

    def 执行(self, 数据上下文: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
        成分 = _表格(数据上下文["成分评估"])
        配置 = 数据上下文["用途配置"]
        HSP结果 = _表格(数据上下文["HSP结果"])
        设置 = dict(数据上下文.get("配方设置") or {})
        物性 = 数据上下文["配方物性"]
        RI = 物性["混合折射率"]
        混合RI = RI["值"]
        摘要 = pd.DataFrame([{
            "用途标识": 用途标识,
            "目标折射率": 配置["目标折射率"],
            "混合液实测RI": 混合RI if RI["状态"] == "已实测" else None,
            "混合液预测RI": 混合RI if RI["状态"] == "已预测" else None,
            "混合液采用RI": 混合RI,
            "混合液RI状态": "已有实验值" if RI["状态"] == "已实测" else ("已预测；待实验验证" if RI["状态"] == "已预测" else "待补：" + RI["状态"]),
            "混合液RI方法": RI["方法"],
            "混合液RI与目标差值": round(混合RI - 配置["目标折射率"], 6) if 混合RI is not None else pd.NA,
            "成分数": len(成分),
            "待补浓度成分数": int(成分["浓度状态"].eq("待补浓度").sum()) if not 成分.empty else 0,
            "待指定角色成分数": int(成分["角色状态"].eq("待指定").sum()) if not 成分.empty else 0,
            "HSP已计算条数": int(HSP结果.get("HSP状态", pd.Series(dtype=str)).eq("已计算").sum()),
            "HSP待补条数": int(HSP结果.get("HSP状态", pd.Series(dtype=str)).eq("无法评估").sum()),
            "混溶性实验状态": str(设置.get("实验混溶性") or "待实验"),
            "稳定性状态": str(设置.get("稳定性状态") or "待实验"),
            "水触发相分离": str(设置.get("水触发相分离") or "待实验"),
            "脱钙/脱脂/胶原步骤": "按成分角色分别记录，不合成为透明化总分",
        }])
        for 指标, 结果 in 物性.items():
            for 字段 in ("值", "单位", "状态", "方法", "模型版本", "置信度"):
                摘要[f"物性_{指标}_{字段}"] = [结果[字段]]
        return 摘要, HSP结果


class 颅骨透明化实验终点评价插件(基础插件接口):
    插件标识 = "颅骨透明化实验终点评价"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        记录 = _表格(数据上下文.get("实验记录"))
        if 记录.empty:
            return pd.DataFrame(columns=["终点", "数值", "单位", "状态", "说明"])
        for 列 in ("终点", "数值", "单位", "数据来源", "备注"):
            if 列 not in 记录:
                记录[列] = ""
        记录["终点"] = 记录["终点"].astype(str).str.strip()
        记录["数值"] = pd.to_numeric(记录["数值"], errors="coerce")
        记录["状态"] = 记录.apply(lambda 行: "已记录" if 行["终点"] in 实验终点字段 and pd.notna(行["数值"]) else "待补或不支持的终点", axis=1)
        记录["说明"] = 记录["状态"].map({"已记录": "实验终点，仅作为真实标签，不参与虚构预测", "待补或不支持的终点": "请使用支持的终点并填写数值"})
        return 记录


class 颅骨透明化配方特征构建插件(基础插件接口):
    插件标识 = "颅骨透明化配方特征构建"

    def 执行(self, 数据上下文: dict[str, Any]) -> dict[str, Any]:
        摘要 = _表格(数据上下文["配方摘要"])
        HSP = _表格(数据上下文["HSP结果"])
        实验 = _表格(数据上下文["实验终点"])
        特征 = 摘要.copy()
        缺项: list[str] = []
        行 = 特征.iloc[0]
        if int(行["待补浓度成分数"]) > 0:
            缺项.append("成分浓度")
        if int(行["待指定角色成分数"]) > 0:
            缺项.append("成分角色")
        if str(行["混合液RI状态"]).startswith("待补"):
            缺项.append("混合液RI")
        if HSP.empty or int(行["HSP已计算条数"]) == 0:
            缺项.append("HSP参照或参数")
        return {
            "配方摘要": 特征,
            "缺失项": 缺项,
            "有效实验终点数": int(实验.get("状态", pd.Series(dtype=str)).eq("已记录").sum()),
        }


class 颅骨透明化用途约束插件(基础插件接口):
    插件标识 = "颅骨透明化用途约束"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        配置 = 数据上下文["用途配置"]
        物性 = 数据上下文["配方物性"]
        阈值 = 配置.get("物性约束") or {}
        if set(阈值) - set(物性):
            raise ValueError("物性约束包含未知指标")
        行们 = []
        for 指标, 结果 in 物性.items():
            约束 = 阈值.get(指标, {})
            if set(约束) - {"最小", "最大"}:
                raise ValueError(f"{指标}约束只支持最小和最大")
            下限, 上限 = 约束.get("最小"), 约束.get("最大")
            下限 = None if 下限 is None else 有限数(下限, f"{指标}最小")
            上限 = None if 上限 is None else 有限数(上限, f"{指标}最大")
            if 下限 is not None and 上限 is not None and 下限 > 上限:
                raise ValueError(f"{指标}约束最小值不能大于最大值")
            值 = 结果["值"]
            状态 = "未知" if 值 is None else "未设置阈值"
            if 值 is not None and (下限 is not None or 上限 is not None):
                通过 = (下限 is None or 值 >= 下限) and (上限 is None or 值 <= 上限)
                状态 = "通过" if 通过 else "不通过"
            行们.append({"指标": 指标, "值": 值, "单位": 结果["单位"], "证据状态": 结果["状态"], "约束状态": 状态,
                         "目标值": 配置["目标折射率"] if 指标 == "混合折射率" else None, "最小": 下限, "最大": 上限})
        for 指标 in ("组织有效扩散", "局部滞留", "washout", "局部毒性", "全身毒性"):
            行们.append({"指标": 指标, "值": None, "证据状态": "待独立递送或毒理证据", "约束状态": "未知"})
        return pd.DataFrame(行们)


class 颅骨透明化用途运行器:
    """旧入口兼容适配；实际编排在核心系统。"""

    def 运行(self, 成分: pd.DataFrame, 用途配置: dict[str, Any], HSP参照: pd.DataFrame | None = None, 配方设置: dict[str, Any] | None = None, 实验记录: pd.DataFrame | None = None) -> dict[str, pd.DataFrame | dict[str, Any]]:
        from 核心系统.配方评估流程 import 运行颅骨透明化流程
        return 运行颅骨透明化流程({
            "成分": 成分,
            "用途配置": 用途配置,
            "HSP参照": pd.DataFrame() if HSP参照 is None else HSP参照,
            "配方设置": 配方设置 or {},
            "实验记录": pd.DataFrame() if 实验记录 is None else 实验记录,
        })
