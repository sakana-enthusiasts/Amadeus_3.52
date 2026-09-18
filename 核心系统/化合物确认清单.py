"""把一次候选流程的已确认化合物固化为可追溯快照。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd

from 核心系统.数据管理接口 import 文件数据访问管理器
from 插件.颅骨透明化.颅骨透明化用途插件 import 默认用途配置, 用途标识


确认目录标识 = "化合物确认批次目录"
草稿目录标识 = "化合物工作草稿目录"
草稿成分标识 = "化合物工作草稿成分"
颅骨专用字段默认值 = {
    "纯物质RI": pd.NA, "eRI": pd.NA, "浓度下RI": pd.NA, "实验水合评分": pd.NA,
    "HSP_dD": pd.NA, "HSP_dP": pd.NA, "HSP_dH": pd.NA, "水中溶解度": pd.NA,
    "BA中溶解度": pd.NA, "VA中溶解度": pd.NA, "AqIS中溶解度": pd.NA,
    "预测混溶性": "", "实验混溶性": "", "沉淀": "", "浑浊": "", "分层": "", "分层时间": "",
    "颜色": "", "颜色变化": "", "吸收峰_nm": pd.NA, "pH": pd.NA,
    "脱钙证据": "", "脱脂证据": "", "胶原处理证据": "", "数据来源": "",
}


def _草稿默认用途字段() -> dict[str, Any]:
    """当前 MVP 只有颅骨透明化用途，但格式已可扩展至后续用途。"""
    return 默认用途配置()


def _读取(管理器: Any, 方法: str, 标识: str, run_id: str | None = None) -> pd.DataFrame:
    try:
        if run_id is None:
            return getattr(管理器, 方法)(标识)
        return getattr(管理器, 方法)(标识, run_id=run_id)
    except FileNotFoundError:
        return pd.DataFrame()


def 可确认候选(数据管理器: Any, run_id: str) -> pd.DataFrame:
    """合并本轮筛选和身份结果，供用户明确选择后固化。"""
    筛选 = _读取(数据管理器, "读取筛选结果", "用户导入_规则筛选结果", run_id)
    if 筛选.empty:
        raise FileNotFoundError(f"运行 {run_id} 没有候选筛选结果")
    身份 = _读取(数据管理器, "读取中间结果", "用户导入_化合物身份映射", run_id)
    身份字段 = ["候选编号", "PubChem CID", "InChIKey", "Canonical SMILES", "Isomeric SMILES", "分子式", "匹配状态", "冲突说明", "是否为盐", "是否为水合物或溶剂化物", "是否为混合物"]
    if not 身份.empty:
        可用身份字段 = [字段 for 字段 in 身份字段 if 字段 in 身份.columns]
        筛选 = 筛选.merge(身份[可用身份字段], on="候选编号", how="left", validate="one_to_one")
    for 字段 in 身份字段:
        if 字段 not in 筛选:
            筛选[字段] = ""
    return 筛选


def 创建确认清单(
    数据管理器: Any,
    run_id: str,
    候选编号: Iterable[str],
    清单名称: str,
    清单用途: str,
    确认备注: str = "",
) -> tuple[dict[str, Any], pd.DataFrame]:
    """创建一份新增式快照；既不覆盖候选结果，也不更新旧快照。"""
    候选 = 可确认候选(数据管理器, run_id)
    已选 = {str(值) for 值 in 候选编号}
    清单 = 候选[候选["候选编号"].astype(str).isin(已选)].copy()
    if not 已选:
        raise ValueError("至少选择一个候选后才能创建确认清单")
    缺失 = sorted(已选 - set(清单["候选编号"].astype(str)))
    if 缺失:
        raise ValueError(f"所选候选不属于运行 {run_id}：{缺失}")
    时间 = datetime.now(timezone.utc)
    批次编号 = f"batch_{时间:%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
    清单标识 = f"化合物确认清单_{批次编号}"
    清单.insert(0, "批次编号", 批次编号)
    清单.insert(1, "来源运行编号", str(run_id))
    清单.insert(2, "确认清单标识", 清单标识)
    清单.insert(3, "清单名称", 清单名称.strip() or "未命名确认清单")
    清单.insert(4, "清单用途", 清单用途)
    清单.insert(5, "确认时间", 时间.isoformat())
    清单.insert(6, "确认状态", "已确认")
    清单.insert(7, "确认备注", 确认备注.strip())
    数据管理器.保存筛选结果(清单标识, 清单, run_id=run_id)
    元数据 = {
        "批次编号": 批次编号,
        "来源运行编号": str(run_id),
        "确认清单标识": 清单标识,
        "清单名称": 清单.iloc[0]["清单名称"],
        "清单用途": 清单用途,
        "确认时间": 时间.isoformat(),
        "确认成分数": len(清单),
        "确认备注": 确认备注.strip(),
        "存储位置": "运行",
    }
    目录 = _读取(数据管理器, "读取软件数据库表格", f"{确认目录标识}.csv")
    目录 = pd.concat([目录, pd.DataFrame([元数据])], ignore_index=True) if not 目录.empty else pd.DataFrame([元数据])
    数据管理器.保存软件数据库表格(f"{确认目录标识}.csv", 目录)
    return 元数据, 清单


def 获取当前工作草稿(数据管理器: Any) -> tuple[dict[str, Any], pd.DataFrame]:
    """取得可覆盖的工作草稿；草稿不是历史批次。"""
    目录 = _读取(数据管理器, "读取软件数据库表格", f"{草稿目录标识}.csv")
    开放 = 目录[目录.get("状态", pd.Series(dtype=str)).astype(str).eq("进行中")] if not 目录.empty else pd.DataFrame()
    if 开放.empty:
        时间 = datetime.now(timezone.utc)
        元数据 = {"草稿编号": f"draft_{时间:%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}", "创建时间": 时间.isoformat(), "更新时间": 时间.isoformat(), "状态": "进行中", **_草稿默认用途字段()}
        目录 = pd.concat([目录, pd.DataFrame([元数据])], ignore_index=True) if not 目录.empty else pd.DataFrame([元数据])
        数据管理器.保存软件数据库表格(f"{草稿目录标识}.csv", 目录)
    else:
        元数据 = 开放.iloc[-1].to_dict()
        缺少用途字段 = {键: 值 for 键, 值 in _草稿默认用途字段().items() if 键 not in 元数据 or pd.isna(元数据[键]) or str(元数据[键]).strip() == ""}
        if 缺少用途字段:
            元数据 |= 缺少用途字段
            for 键, 值 in 缺少用途字段.items():
                目录.loc[目录["草稿编号"].astype(str).eq(str(元数据["草稿编号"])), 键] = 值
            数据管理器.保存软件数据库表格(f"{草稿目录标识}.csv", 目录)
    成分 = _读取(数据管理器, "读取软件数据库表格", f"{草稿成分标识}.csv")
    成分 = 成分[成分.get("草稿编号", pd.Series(dtype=str)).astype(str).eq(str(元数据["草稿编号"]))].copy() if not 成分.empty else pd.DataFrame()
    return 元数据, 成分


def 设置工作草稿用途配置(数据管理器: Any, 草稿编号: str, 用途配置: dict[str, Any]) -> dict[str, Any]:
    """用途在工作清单开始时确定，后续追加候选自动继承。"""
    配置 = _草稿默认用途字段() | dict(用途配置 or {})
    if 配置.get("用途标识") != 用途标识:
        raise ValueError("当前版本仅支持颅骨透明化用途")
    目标RI = pd.to_numeric(pd.Series([配置.get("目标折射率")]), errors="coerce").iloc[0]
    if pd.isna(目标RI) or not 1.0 < float(目标RI) < 2.0:
        raise ValueError("目标折射率必须是 1.0 至 2.0 之间的数值")
    配置["目标折射率"] = float(目标RI)
    目录 = _读取(数据管理器, "读取软件数据库表格", f"{草稿目录标识}.csv")
    命中 = 目录[目录.get("草稿编号", pd.Series(dtype=str)).astype(str).eq(str(草稿编号))]
    if len(命中) != 1 or str(命中.iloc[0].get("状态", "")) != "进行中":
        raise ValueError("未找到可更新的进行中工作草稿")
    for 键, 值 in 配置.items():
        目录.loc[目录["草稿编号"].astype(str).eq(str(草稿编号)), 键] = 值
    目录.loc[目录["草稿编号"].astype(str).eq(str(草稿编号)), "更新时间"] = datetime.now(timezone.utc).isoformat()
    数据管理器.保存软件数据库表格(f"{草稿目录标识}.csv", 目录)
    return 目录.loc[目录["草稿编号"].astype(str).eq(str(草稿编号))].iloc[0].to_dict()


def 保存工作草稿成分(数据管理器: Any, 草稿编号: str, 成分: pd.DataFrame) -> pd.DataFrame:
    """覆盖当前草稿的组成，不触碰任何已确认历史批次。"""
    必需 = {"候选编号", "化学名称", "CAS", "浓度值", "浓度单位", "是否纳入颅骨透明化计算"}
    缺失 = 必需 - set(成分.columns)
    if 缺失:
        raise ValueError(f"工作草稿缺少字段：{sorted(缺失)}")
    成分 = 成分.copy()
    成分["草稿编号"] = str(草稿编号)
    成分["浓度值"] = pd.to_numeric(成分["浓度值"], errors="coerce")
    成分["浓度单位"] = 成分["浓度单位"].fillna("").astype(str).str.strip()
    成分["是否纳入颅骨透明化计算"] = 成分["是否纳入颅骨透明化计算"].fillna(False).astype(str).str.casefold().isin({"true", "1", "是"})
    if "颅骨透明化角色" not in 成分:
        成分["颅骨透明化角色"] = "未指定"
    成分["颅骨透明化角色"] = 成分["颅骨透明化角色"].fillna("未指定").astype(str).str.strip().replace("", "未指定")
    # 保留既有字段取值，避免影响已接入该字段的历史/毒理读取；新状态另列说明。
    成分["透明化计算接口状态"] = 成分["是否纳入颅骨透明化计算"].map({True: "已预留，待接入", False: "未选择"})
    成分["颅骨透明化用途状态"] = 成分["是否纳入颅骨透明化计算"].map({True: "已接入用途链，待运行评估", False: "未纳入"})
    for 字段, 默认值 in 颅骨专用字段默认值.items():
        if 字段 not in 成分:
            成分[字段] = 默认值
    if "成分键" not in 成分:
        成分["成分键"] = 成分.get("来源运行编号", "").astype(str) + "::" + 成分["候选编号"].astype(str)
    全部 = _读取(数据管理器, "读取软件数据库表格", f"{草稿成分标识}.csv")
    保留 = 全部[~全部.get("草稿编号", pd.Series(dtype=str)).astype(str).eq(str(草稿编号))] if not 全部.empty else pd.DataFrame()
    输出 = pd.concat([保留, 成分], ignore_index=True) if not 保留.empty else 成分
    数据管理器.保存软件数据库表格(f"{草稿成分标识}.csv", 输出)
    目录 = _读取(数据管理器, "读取软件数据库表格", f"{草稿目录标识}.csv")
    if not 目录.empty:
        目录.loc[目录["草稿编号"].astype(str).eq(str(草稿编号)), "更新时间"] = datetime.now(timezone.utc).isoformat()
        数据管理器.保存软件数据库表格(f"{草稿目录标识}.csv", 目录)
    return 成分


def 向工作草稿追加候选(数据管理器: Any, run_id: str, 候选编号: Iterable[str]) -> tuple[dict[str, Any], pd.DataFrame]:
    """把当前运行中选中的候选追加到草稿；同一来源候选可在草稿中更新。"""
    元数据, 现有 = 获取当前工作草稿(数据管理器)
    候选 = 可确认候选(数据管理器, run_id)
    已选 = {str(值) for 值 in 候选编号}
    新增 = 候选[候选["候选编号"].astype(str).isin(已选)].copy()
    if 新增.empty:
        raise ValueError("请至少选择一个候选加入工作清单")
    新增["来源运行编号"] = str(run_id)
    新增["CAS"] = 新增.get("CAS号", "").fillna("") if isinstance(新增.get("CAS号", ""), pd.Series) else ""
    新增["浓度值"] = pd.NA
    新增["浓度单位"] = ""
    新增["是否纳入颅骨透明化计算"] = True
    新增["颅骨透明化角色"] = "未指定"
    新增["透明化计算接口状态"] = "已预留，待接入"
    新增["颅骨透明化用途状态"] = "已接入用途链，待运行评估"
    映射 = {
        "纯物质RI": ("实测RI", "纯物质RI"), "eRI": ("eRI",), "实验水合评分": ("水合评分平均值", "实验水合评分"),
        "HSP_dD": ("dD", "HSP_dD"), "HSP_dP": ("dP", "HSP_dP"), "HSP_dH": ("dH", "HSP_dH"),
        "pH": ("预测pH", "pH"), "实验混溶性": ("实际互溶状态", "实验混溶性"),
    }
    for 目标字段, 候选字段 in 映射.items():
        来源字段 = next((字段 for 字段 in 候选字段 if 字段 in 新增.columns), None)
        新增[目标字段] = 新增[来源字段] if 来源字段 else 颅骨专用字段默认值[目标字段]
    for 字段, 默认值 in 颅骨专用字段默认值.items():
        if 字段 not in 新增:
            新增[字段] = 默认值
    合并 = pd.concat([现有, 新增], ignore_index=True) if not 现有.empty else 新增
    合并 = 合并.drop_duplicates(subset=["来源运行编号", "候选编号"], keep="last")
    return 元数据, 保存工作草稿成分(数据管理器, str(元数据["草稿编号"]), 合并)


def 确认工作草稿(
    数据管理器: Any,
    草稿编号: str,
    清单名称: str,
    清单用途: str,
    确认备注: str = "",
    用途配置: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """将跨运行的草稿一次性固化为全局确认批次。"""
    元数据, 成分 = 获取当前工作草稿(数据管理器)
    if str(元数据["草稿编号"]) != str(草稿编号) or 成分.empty:
        raise ValueError("当前没有可确认的化合物工作草稿")
    成分 = 成分.copy()
    配置 = _草稿默认用途字段() | {键: 元数据.get(键, 值) for 键, 值 in _草稿默认用途字段().items()} | dict(用途配置 or {})
    if 配置.get("用途标识") != 用途标识:
        raise ValueError("当前版本仅支持颅骨透明化用途")
    成分["浓度值"] = pd.to_numeric(成分["浓度值"], errors="coerce")
    无浓度 = 成分[成分["浓度值"].isna() | 成分["浓度值"].le(0) | 成分["浓度单位"].astype(str).str.strip().eq("")]
    if not 无浓度.empty:
        raise ValueError("所有确认成分都必须填写浓度值和浓度单位")
    时间 = datetime.now(timezone.utc)
    批次编号 = f"batch_{时间:%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
    清单标识 = f"化合物确认清单_{批次编号}"
    清单 = 成分.copy()
    清单.insert(0, "批次编号", 批次编号)
    清单.insert(1, "确认清单标识", 清单标识)
    清单.insert(2, "清单名称", 清单名称.strip() or "未命名确认清单")
    清单.insert(3, "清单用途", 清单用途)
    清单.insert(4, "用途标识", 配置["用途标识"])
    清单.insert(5, "用途配置版本", 配置["用途配置版本"])
    清单.insert(6, "目标折射率", 配置["目标折射率"])
    清单.insert(7, "HSP参照体系", 配置["HSP参照体系"])
    清单.insert(8, "确认时间", 时间.isoformat())
    清单.insert(9, "确认状态", "已确认")
    清单.insert(10, "确认备注", 确认备注.strip())
    全局管理器 = 文件数据访问管理器(数据管理器.项目根目录)
    全局管理器.保存筛选结果(清单标识, 清单)
    结果元数据 = {
        "批次编号": 批次编号, "来源运行编号": "多个运行", "确认清单标识": 清单标识, "清单名称": 清单.iloc[0]["清单名称"],
        "清单用途": 清单用途, "用途标识": 配置["用途标识"], "用途配置版本": 配置["用途配置版本"], "目标折射率": 配置["目标折射率"], "HSP参照体系": 配置["HSP参照体系"], "确认时间": 时间.isoformat(), "确认成分数": len(清单), "确认备注": 确认备注.strip(), "存储位置": "全局",
    }
    确认目录 = _读取(数据管理器, "读取软件数据库表格", f"{确认目录标识}.csv")
    确认目录 = pd.concat([确认目录, pd.DataFrame([结果元数据])], ignore_index=True) if not 确认目录.empty else pd.DataFrame([结果元数据])
    数据管理器.保存软件数据库表格(f"{确认目录标识}.csv", 确认目录)
    草稿目录 = _读取(数据管理器, "读取软件数据库表格", f"{草稿目录标识}.csv")
    草稿目录.loc[草稿目录["草稿编号"].astype(str).eq(str(草稿编号)), "状态"] = "已确认"
    草稿目录.loc[草稿目录["草稿编号"].astype(str).eq(str(草稿编号)), "确认批次编号"] = 批次编号
    数据管理器.保存软件数据库表格(f"{草稿目录标识}.csv", 草稿目录)
    # 确认后的描述符、配方聚合和颅骨用途评估均以该冻结批次为输入，不再要求重录化合物。
    from 核心系统.颅骨透明化用途 import 确认后自动处理
    后处理 = 确认后自动处理(全局管理器, 批次编号, 清单, 配置)
    结果元数据["确认后处理状态"] = "已完成"
    结果元数据["描述符记录数"] = 后处理["描述符记录数"]
    结果元数据["配方特征状态"] = 后处理["配方特征状态"]
    确认目录 = _读取(数据管理器, "读取软件数据库表格", f"{确认目录标识}.csv")
    确认目录.loc[确认目录["批次编号"].astype(str).eq(批次编号), "确认后处理状态"] = "已完成"
    确认目录.loc[确认目录["批次编号"].astype(str).eq(批次编号), "描述符记录数"] = 后处理["描述符记录数"]
    确认目录.loc[确认目录["批次编号"].astype(str).eq(批次编号), "配方特征状态"] = 后处理["配方特征状态"]
    数据管理器.保存软件数据库表格(f"{确认目录标识}.csv", 确认目录)
    return 结果元数据, 清单


def 已确认清单目录(数据管理器: Any) -> pd.DataFrame:
    """列出仍可读取的确认快照；失效路径不会作为下游输入。"""
    目录 = _读取(数据管理器, "读取软件数据库表格", f"{确认目录标识}.csv")
    if 目录.empty:
        return 目录
    有效 = []
    for _, 行 in 目录.iterrows():
        if str(行.get("存储位置", "运行")) == "全局":
            全局管理器 = 文件数据访问管理器(数据管理器.项目根目录)
            清单 = _读取(全局管理器, "读取筛选结果", str(行["确认清单标识"]))
        else:
            清单 = _读取(数据管理器, "读取筛选结果", str(行["确认清单标识"]), str(行["来源运行编号"]))
        有效.append(not 清单.empty)
    return 目录.loc[有效].copy().reset_index(drop=True)


def 读取确认清单(数据管理器: Any, 批次编号: str) -> tuple[dict[str, Any], pd.DataFrame]:
    目录 = 已确认清单目录(数据管理器)
    命中 = 目录[目录["批次编号"].astype(str).eq(str(批次编号))]
    if len(命中) != 1:
        raise FileNotFoundError(f"未找到有效的化合物确认批次：{批次编号}")
    元数据 = 命中.iloc[0].to_dict()
    if str(元数据.get("存储位置", "运行")) == "全局":
        清单 = _读取(文件数据访问管理器(数据管理器.项目根目录), "读取筛选结果", str(元数据["确认清单标识"]))
    else:
        清单 = _读取(数据管理器, "读取筛选结果", str(元数据["确认清单标识"]), str(元数据["来源运行编号"]))
    return 元数据, 清单
