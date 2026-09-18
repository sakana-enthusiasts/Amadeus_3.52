"""颅骨透明化确认批次的用途数据存取与运行入口。"""

from __future__ import annotations

from typing import Any
import json

import pandas as pd

from 核心系统.数据管理接口 import 文件数据访问管理器
from 插件.化学计算.确认批次描述符插件 import 确认批次描述符插件
from 插件.颅骨透明化.颅骨透明化用途插件 import 默认用途配置, 用途标识
from 核心系统.配方评估流程 import 运行颅骨透明化流程


成分证据标识 = "颅骨透明化成分证据.csv"
HSP参照标识 = "颅骨透明化HSP参照.csv"
配方设置标识 = "颅骨透明化配方设置.csv"
实验记录标识 = "颅骨透明化实验记录.csv"
评估结果标识 = "颅骨透明化评估结果.csv"
HSP结果标识 = "颅骨透明化HSP结果.csv"
配方特征标识 = "颅骨透明化配方特征.csv"
描述符标识 = "确认批次化学描述符.csv"
组分HSP结果标识 = "颅骨透明化组分HSP结果.csv"
配方物性标识 = "颅骨透明化配方物性.csv"
用途约束标识 = "颅骨透明化用途约束.csv"


def _读取(管理器: 文件数据访问管理器, 标识: str) -> pd.DataFrame:
    try:
        return 管理器.读取软件数据库表格(标识)
    except FileNotFoundError:
        return pd.DataFrame()


def _批次过滤(数据: pd.DataFrame, 批次编号: str) -> pd.DataFrame:
    if 数据.empty or "批次编号" not in 数据:
        return pd.DataFrame()
    return 数据.loc[数据["批次编号"].astype(str).eq(str(批次编号))].copy().reset_index(drop=True)


def 默认成分证据(确认清单: pd.DataFrame) -> pd.DataFrame:
    """以已确认批次为唯一成分来源，补充可编辑的颅骨用途字段。"""
    成分 = 确认清单.copy()
    成分["成分键"] = 成分.get("成分键", (成分.get("来源运行编号", "") .astype(str) + "::" + 成分["候选编号"].astype(str)) if "来源运行编号" in 成分 else 成分["候选编号"].astype(str))
    字段默认值 = {
        "颅骨透明化角色": "未指定", "纯物质RI": pd.NA, "eRI": pd.NA, "浓度下RI": pd.NA, "实验水合评分": pd.NA,
        "HSP_dD": pd.NA, "HSP_dP": pd.NA, "HSP_dH": pd.NA, "水中溶解度": pd.NA, "BA中溶解度": pd.NA,
        "VA中溶解度": pd.NA, "AqIS中溶解度": pd.NA, "预测混溶性": "", "实验混溶性": "",
        "沉淀": "", "浑浊": "", "分层": "", "分层时间": "", "颜色": "", "颜色变化": "",
        "吸收峰_nm": pd.NA, "pH": pd.NA, "脱钙证据": "", "脱脂证据": "", "胶原处理证据": "", "数据来源": "",
        "体积分数": pd.NA, "摩尔分数": pd.NA, "纯物质黏度_mPa_s": pd.NA,
        "渗透角色": "", "摩尔浓度_mol_L": pd.NA, "范特霍夫因子": pd.NA,
    }
    for 字段, 默认值 in 字段默认值.items():
        if 字段 not in 成分:
            成分[字段] = 默认值
    保留字段 = ["成分键", "候选编号", "化学名称", "CAS", "浓度值", "浓度单位", *字段默认值]
    return 成分[[字段 for 字段 in 保留字段 if 字段 in 成分]].copy()


def 读取成分证据(管理器: 文件数据访问管理器, 批次编号: str, 确认清单: pd.DataFrame) -> pd.DataFrame:
    默认 = 默认成分证据(确认清单)
    已存 = _批次过滤(_读取(管理器, 成分证据标识), 批次编号)
    if 已存.empty:
        return 默认
    已存 = 已存.drop(columns=["批次编号"], errors="ignore")
    return 默认.drop(columns=[列 for 列 in 默认.columns if 列 in 已存.columns and 列 != "成分键"], errors="ignore").merge(已存, on="成分键", how="left")


def 保存成分证据(管理器: 文件数据访问管理器, 批次编号: str, 数据: pd.DataFrame) -> pd.DataFrame:
    if "成分键" not in 数据:
        raise ValueError("颅骨透明化成分证据缺少成分键")
    新数据 = 数据.copy()
    新数据["批次编号"] = str(批次编号)
    全部 = _读取(管理器, 成分证据标识)
    保留 = 全部.loc[~全部.get("批次编号", pd.Series(dtype=str)).astype(str).eq(str(批次编号))] if not 全部.empty else pd.DataFrame()
    输出 = pd.concat([保留, 新数据], ignore_index=True) if not 保留.empty else 新数据
    管理器.保存软件数据库表格(成分证据标识, 输出)
    return 新数据


def 读取HSP参照(管理器: 文件数据访问管理器, 批次编号: str) -> pd.DataFrame:
    return _批次过滤(_读取(管理器, HSP参照标识), 批次编号)


def 保存HSP参照(管理器: 文件数据访问管理器, 批次编号: str, 数据: pd.DataFrame) -> pd.DataFrame:
    必需 = {"参照体系", "HSP_dD", "HSP_dP", "HSP_dH"}
    if 缺失 := 必需 - set(数据.columns):
        raise ValueError(f"HSP参照缺少字段：{sorted(缺失)}")
    新数据 = 数据.copy()
    新数据["批次编号"] = str(批次编号)
    全部 = _读取(管理器, HSP参照标识)
    保留 = 全部.loc[~全部.get("批次编号", pd.Series(dtype=str)).astype(str).eq(str(批次编号))] if not 全部.empty else pd.DataFrame()
    管理器.保存软件数据库表格(HSP参照标识, pd.concat([保留, 新数据], ignore_index=True) if not 保留.empty else 新数据)
    return 新数据


def 读取配方设置(管理器: 文件数据访问管理器, 批次编号: str) -> dict[str, Any]:
    数据 = _批次过滤(_读取(管理器, 配方设置标识), 批次编号)
    return {} if 数据.empty else 数据.iloc[-1].drop(labels=["批次编号"], errors="ignore").to_dict()


def 保存配方设置(管理器: 文件数据访问管理器, 批次编号: str, 设置: dict[str, Any]) -> dict[str, Any]:
    新设置 = {"批次编号": str(批次编号), **设置}
    for 字段 in ("物性模型选择", "物性模型参数", "物性条件"):
        if isinstance(新设置.get(字段), dict):
            新设置[字段] = json.dumps(新设置[字段], ensure_ascii=False, allow_nan=False)
    全部 = _读取(管理器, 配方设置标识)
    保留 = 全部.loc[~全部.get("批次编号", pd.Series(dtype=str)).astype(str).eq(str(批次编号))] if not 全部.empty else pd.DataFrame()
    管理器.保存软件数据库表格(配方设置标识, pd.concat([保留, pd.DataFrame([新设置])], ignore_index=True) if not 保留.empty else pd.DataFrame([新设置]))
    return 新设置


def 读取实验记录(管理器: 文件数据访问管理器, 批次编号: str) -> pd.DataFrame:
    return _批次过滤(_读取(管理器, 实验记录标识), 批次编号)


def 保存实验记录(管理器: 文件数据访问管理器, 批次编号: str, 数据: pd.DataFrame) -> pd.DataFrame:
    新数据 = 数据.copy()
    新数据["批次编号"] = str(批次编号)
    全部 = _读取(管理器, 实验记录标识)
    保留 = 全部.loc[~全部.get("批次编号", pd.Series(dtype=str)).astype(str).eq(str(批次编号))] if not 全部.empty else pd.DataFrame()
    管理器.保存软件数据库表格(实验记录标识, pd.concat([保留, 新数据], ignore_index=True) if not 保留.empty else 新数据)
    return 新数据


def _按批次保存(管理器: 文件数据访问管理器, 标识: str, 批次编号: str, 数据: pd.DataFrame) -> pd.DataFrame:
    输出 = pd.DataFrame(数据).copy()
    输出["批次编号"] = str(批次编号)
    全部 = _读取(管理器, 标识)
    保留 = 全部.loc[~全部.get("批次编号", pd.Series(dtype=str)).astype(str).eq(str(批次编号))] if not 全部.empty else pd.DataFrame()
    管理器.保存软件数据库表格(标识, pd.concat([保留, 输出], ignore_index=True) if not 保留.empty else 输出)
    return 输出


def 读取确认批次描述符(管理器: 文件数据访问管理器, 批次编号: str) -> pd.DataFrame:
    return _批次过滤(_读取(管理器, 描述符标识), 批次编号)


def 生成确认批次描述符(管理器: 文件数据访问管理器, 批次编号: str, 确认清单: pd.DataFrame) -> pd.DataFrame:
    描述符 = 确认批次描述符插件().执行({"批次编号": 批次编号, "确认清单": 确认清单})
    return _按批次保存(管理器, 描述符标识, 批次编号, 描述符)


def _描述符配方聚合(成分: pd.DataFrame, 描述符: pd.DataFrame) -> pd.DataFrame:
    """只在所有浓度为百分比时给出明确标记的线性筛选近似。"""
    if 成分.empty:
        return pd.DataFrame([{"描述符聚合状态": "无成分"}])
    if 描述符.empty or not {"成分键", "描述符名称", "数值", "是否计算成功"}.issubset(描述符.columns):
        return pd.DataFrame([{"描述符聚合状态": "待生成确认批次描述符", "描述符成功成分数": 0}])
    单位 = 成分.get("浓度单位", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    浓度 = pd.to_numeric(成分.get("浓度值", pd.Series(dtype=float)), errors="coerce")
    百分比 = 单位.str.contains("%|百分", regex=True) & 浓度.notna() & 浓度.gt(0)
    if not 百分比.all():
        return pd.DataFrame([{"描述符聚合状态": "待统一配方比例；mM/% 等混合单位不可安全加权", "描述符成功成分数": int(描述符.get("是否计算成功", pd.Series(dtype=bool)).astype(bool).sum() > 0)}])
    权重 = 浓度 / 浓度.sum()
    成分权重 = pd.DataFrame({"成分键": 成分["成分键"].astype(str), "权重": 权重})
    有效 = 描述符.loc[描述符.get("是否计算成功", pd.Series(dtype=bool)).astype(bool)].copy()
    有效["数值数值型"] = pd.to_numeric(有效.get("数值"), errors="coerce")
    宽表 = 有效.pivot_table(index="成分键", columns="描述符名称", values="数值数值型", aggfunc="first").reset_index()
    合并 = 成分权重.merge(宽表, on="成分键", how="left")
    数值列 = [列 for 列 in 合并.columns if 列 not in {"成分键", "权重"}]
    结果: dict[str, Any] = {"描述符聚合状态": "已按用户填写的百分比作线性筛选近似；不等同于真实混合物物性", "描述符成功成分数": int(合并[数值列].notna().any(axis=1).sum()) if 数值列 else 0}
    for 列 in 数值列:
        有值 = 合并[列].notna()
        if 有值.any():
            归一权重 = 合并.loc[有值, "权重"] / 合并.loc[有值, "权重"].sum()
            结果[f"描述符近似加权_{列}"] = round(float((合并.loc[有值, 列] * 归一权重).sum()), 6)
    return pd.DataFrame([结果])


def 运行用途评估(管理器: 文件数据访问管理器, 批次编号: str, 确认清单: pd.DataFrame, 用途配置: dict[str, Any] | None = None) -> dict[str, Any]:
    配置 = 默认用途配置() | dict(用途配置 or {})
    if 配置.get("用途标识") != 用途标识:
        raise ValueError("仅可运行颅骨透明化用途评估")
    结果 = 运行颅骨透明化流程({
        "成分": 读取成分证据(管理器, 批次编号, 确认清单), "用途配置": 配置,
        "HSP参照": 读取HSP参照(管理器, 批次编号), "配方设置": 读取配方设置(管理器, 批次编号),
        "实验记录": 读取实验记录(管理器, 批次编号), "配方编号": str(批次编号),
    })
    描述符 = 读取确认批次描述符(管理器, 批次编号)
    聚合描述符 = _描述符配方聚合(pd.DataFrame(结果["成分评估"]), 描述符)
    结果["配方特征"] = pd.concat([pd.DataFrame(结果["配方特征"]).reset_index(drop=True), 聚合描述符.reset_index(drop=True)], axis=1)
    for 标识, 数据 in ((评估结果标识, 结果["配方摘要"]), (HSP结果标识, 结果["HSP结果"]), (组分HSP结果标识, 结果["组分HSP结果"]), (配方特征标识, 结果["配方特征"])):
        _按批次保存(管理器, 标识, 批次编号, pd.DataFrame(数据))
    物性表 = 结果["配方物性"].copy()
    for 列 in ("警告", "依赖", "条件", "模型参数"):
        物性表[列] = 物性表[列].map(lambda 值: json.dumps(值, ensure_ascii=False, allow_nan=False))
    _按批次保存(管理器, 配方物性标识, 批次编号, 物性表)
    _按批次保存(管理器, 用途约束标识, 批次编号, 结果["用途约束"])
    return 结果


def 确认后自动处理(管理器: 文件数据访问管理器, 批次编号: str, 确认清单: pd.DataFrame, 用途配置: dict[str, Any]) -> dict[str, Any]:
    """确认清单后只做自动计算/聚合；不要求再次录入成分。"""
    描述符 = 生成确认批次描述符(管理器, 批次编号, 确认清单)
    评估 = 运行用途评估(管理器, 批次编号, 确认清单, 用途配置)
    return {"描述符记录数": len(描述符), "配方特征状态": str(pd.DataFrame(评估["配方特征"]).iloc[0].get("预测器输入状态", ""))}
