"""毒理分析页面：本地证据录入、三态条件和可解释匹配。"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.化合物确认清单 import 已确认清单目录, 读取确认清单
from 核心系统.运行数据管理 import 运行数据管理器
from 核心系统.毒理分析 import (
    不作为条件,
    指定,
    未知,
    可匹配字段,
    字段标签,
    默认会话,
    默认匹配策略,
    默认来源策略,
    规范化会话,
)
from 核心系统.流程控制器 import 创建颅骨透明化筛选流程控制器


项目根目录 = Path(__file__).resolve().parents[1]
人工证据字段 = [
    "候选编号", "化学名称", "CAS", "证据来源类型", "来源名称或文献", "来源编号或链接", "物种", "品系", "性别",
    "生命周期阶段", "年龄_天", "体重_g", "基因型", "给药途径", "给药频率", "暴露时长_天", "观察时长_天", "恢复期_天",
    "毒性终点", "关注器官或特殊问题", "剂量", "剂量单位", "结果", "可信度", "可追溯性", "备注",
]


def _读取(管理器: 文件数据访问管理器, 标识: str) -> pd.DataFrame:
    try:
        return 管理器.读取筛选结果(标识)
    except FileNotFoundError:
        return pd.DataFrame()


def _读取会话(管理器: 文件数据访问管理器) -> dict[str, Any]:
    try:
        原始 = 管理器.读取软件数据库表格("毒理分析会话.csv")
        if not 原始.empty:
            return 规范化会话(json.loads(str(原始.iloc[0]["会话JSON"])))
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
    return 默认会话()


def _保存会话(管理器: 文件数据访问管理器, 会话: dict[str, Any]) -> None:
    管理器.保存软件数据库表格("毒理分析会话.csv", pd.DataFrame([{
        "会话JSON": json.dumps(会话, ensure_ascii=False),
        "说明": "毒理分析会话；公开数据库连接仅保留接口。",
    }]))


def _读取历史上传(文件: Any) -> pd.DataFrame:
    """只导入用户选择的本地文件；不进行任何网络查询。"""
    内容 = 文件.getvalue()
    if str(文件.name).lower().endswith(".xlsx"):
        return pd.read_excel(BytesIO(内容), dtype=str).fillna("")
    for 编码 in ("utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(BytesIO(内容), dtype=str, encoding=编码, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别 CSV 编码，请保存为 UTF-8 或 GB18030 后重试。")


def _条件控件(字段: str, 会话: dict[str, Any]) -> dict[str, Any]:
    当前 = 会话["条件"][字段]
    左, 右 = st.columns((1, 2))
    状态 = 左.selectbox(f"{字段标签[字段]}状态", (指定, 不作为条件, 未知), index=(指定, 不作为条件, 未知).index(当前["状态"]), key=f"毒理状态_{字段}")
    值 = 右.text_input(f"{字段标签[字段]}值", value=str(当前.get("值", "")), disabled=状态 != 指定, key=f"毒理值_{字段}")
    return {"状态": 状态, "值": 值}


def 渲染毒性评估页面() -> None:
    st.header("毒理证据匹配")
    st.caption("只使用本地历史数据和人工录入证据；不把 GHS 或接口占位转换为动物/人体安全结论，也不生成综合风险分数。")
    管理器 = 文件数据访问管理器(项目根目录)
    运行管理器 = 运行数据管理器(项目根目录)
    会话 = _读取会话(管理器)

    with st.expander("1. 证据来源策略", expanded=True):
        预设列表 = ("本地优先", "混合模式", "公共库优先")
        当前预设 = 会话["来源策略"].get("来源预设", "本地优先")
        来源预设 = st.selectbox("来源预设（界面预设）", 预设列表, index=预设列表.index(当前预设))
        来源策略 = 默认来源策略(来源预设)
        来源策略["是否允许缓存结果"] = st.checkbox("允许使用本地缓存", value=bool(会话["来源策略"].get("是否允许缓存结果", True)))
        来源策略["是否允许人工补录证据"] = st.checkbox("允许人工补录证据", value=bool(会话["来源策略"].get("是否允许人工补录证据", True)))
        启用PubChem = st.checkbox("启用 PubChem GHS 危险提示查询", value="PubChem GHS" in set(会话["来源策略"].get("启用公开数据源") or []))
        来源策略["启用公开数据源"] = ["PubChem GHS"] if 启用PubChem else []
        来源策略["是否查询公开库"] = 启用PubChem
        st.info("当前实际接入：PubChem GHS。它输出危险提示、原始响应和查询日志，但不作为动物实验毒理证据参与 A/B/C/D 匹配。CompTox / ToxRefDB、CE 等仍仅保留接口。")

    with st.expander("2. 共享分析条件", expanded=True):
        st.caption("每个字段都有三种语义：指定值才参与比较；不作为条件不扣级；未知不会被系统当作匹配成功。")
        条件 = {字段: _条件控件(字段, 会话) for 字段 in 可匹配字段}

    with st.expander("3. A/B/C/D 匹配策略", expanded=True):
        默认策略 = 默认匹配策略() | 会话["匹配策略"]
        策略 = dict(默认策略)
        for 等级, 说明 in (("A", "严格匹配"), ("B", "可比匹配"), ("C", "探索匹配")):
            策略[f"{等级}级字段"] = st.multiselect(f"{等级}级：{说明}时必须比较的字段", 可匹配字段, default=默认策略[f"{等级}级字段"], format_func=lambda 值: 字段标签[值], key=f"毒理{等级}级字段")
        列1, 列2, 列3 = st.columns(3)
        策略["年龄容差_天"] = 列1.number_input("年龄容差（天）", min_value=0.0, value=float(默认策略["年龄容差_天"]))
        策略["体重容差_g"] = 列2.number_input("体重容差（g）", min_value=0.0, value=float(默认策略["体重容差_g"]))
        策略["暴露时长容差比例"] = 列3.number_input("暴露时长容差", min_value=0.0, max_value=1.0, value=float(默认策略["暴露时长容差比例"]), format="%.2f")
        策略["排除基因敲除或转基因"] = st.checkbox("排除基因敲除/转基因记录", value=bool(默认策略["排除基因敲除或转基因"]))
        策略["无A级显示B级"] = st.checkbox("没有 A 级时显示 B 级", value=bool(默认策略["无A级显示B级"]))
        策略["无AB级显示C级"] = st.checkbox("没有 A/B 级时显示 C 级", value=bool(默认策略["无AB级显示C级"]))
        策略["允许自动降级"] = st.checkbox("允许按策略自动降级", value=bool(默认策略["允许自动降级"]))
        st.caption("用户未填写的字段会标记为“未比较”；记录未报告已指定字段时只会列为 D 级参考或数据缺口，绝不会被当作 A 级匹配。关闭自动降级后，不会展示 B/C 级结果。")

    with st.expander("4. 已确认化合物批次", expanded=True):
        清单目录 = 已确认清单目录(运行管理器)
        旧批次编号 = str(会话.get("化合物批次", {}).get("批次编号", ""))
        if 清单目录.empty:
            化合物批次, 化合物清单 = {}, []
            st.warning("尚无已确认化合物清单。请先在“用户候选导入与配置化筛选”完成一轮运行，并在输出结果中确认生成批次快照。")
        else:
            选项 = 清单目录["批次编号"].astype(str).tolist()
            当前序号 = 选项.index(旧批次编号) if 旧批次编号 in 选项 else 0
            批次编号 = st.selectbox("选择前序确认批次", 选项, index=当前序号, format_func=lambda 值: f"{值}｜{清单目录.loc[清单目录['批次编号'].astype(str).eq(值), '清单名称'].iloc[0]}")
            化合物批次, 已确认清单 = 读取确认清单(运行管理器, 批次编号)
            化合物清单 = [
                {"候选编号": str(行.get("候选编号", "")), "化学名称": str(行.get("化学名称", "")), "CAS": str(行.get("CAS号", 行.get("CAS", ""))), "PubChem CID": str(行.get("PubChem CID", "")), "InChIKey": str(行.get("InChIKey", "")), "Canonical SMILES": str(行.get("Canonical SMILES", "")), "浓度值": 行.get("浓度值", ""), "浓度单位": str(行.get("浓度单位", "")), "是否纳入颅骨透明化计算": str(行.get("是否纳入颅骨透明化计算", "")), "透明化计算接口状态": str(行.get("透明化计算接口状态", "")), "确认状态": str(行.get("确认状态", ""))}
                for _, 行 in 已确认清单.iterrows()
            ]
            st.caption(f"来源运行：{化合物批次['来源运行编号']}；确认时间：{化合物批次['确认时间']}；此快照不会随原候选结果改变。")
            st.dataframe(pd.DataFrame(化合物清单), use_container_width=True, hide_index=True)

    新会话 = 规范化会话({"来源策略": 来源策略, "条件": 条件, "匹配策略": 策略, "化合物批次": 化合物批次, "化合物清单": 化合物清单})
    if st.button("保存毒理分析设置", type="primary"):
        _保存会话(管理器, 新会话)
        st.success("已保存毒理分析设置。")

    st.subheader("人工补录证据与本地历史证据")
    st.caption("可在下表补录；来源类型建议填写“人工录入”或“本地历史数据”，并保留来源编号或链接以便追溯。")
    人工证据 = _读取(管理器, "毒理人工证据")
    if 人工证据.empty:
        人工证据 = pd.DataFrame(columns=人工证据字段)
    for 字段 in 人工证据字段:
        if 字段 not in 人工证据:
            人工证据[字段] = ""
    编辑后证据 = st.data_editor(人工证据[人工证据字段], num_rows="dynamic", use_container_width=True, hide_index=True, key="毒理人工证据编辑器")
    历史上传 = st.file_uploader("导入本地历史证据（CSV / XLSX，可选）", type=("csv", "xlsx"), key="毒理历史证据上传")
    if 历史上传 is not None and st.button("保存本地历史证据"):
        try:
            历史证据 = _读取历史上传(历史上传)
            for 字段 in 人工证据字段:
                if 字段 not in 历史证据:
                    历史证据[字段] = ""
            历史证据 = 历史证据[人工证据字段]
            历史证据.loc[历史证据["证据来源类型"].astype(str).str.strip().eq(""), "证据来源类型"] = "本地历史数据"
            管理器.保存筛选结果("毒理历史证据", 历史证据)
            st.success(f"已保存 {len(历史证据)} 条本地历史证据。")
        except (ValueError, pd.errors.ParserError) as 错误:
            st.error(f"历史证据未导入：{错误}")
    左, 右 = st.columns(2)
    if 左.button("保存人工/本地证据"):
        管理器.保存筛选结果("毒理人工证据", 编辑后证据)
        st.success("证据已保存。")
    if 右.button("保存并运行毒理匹配", type="primary"):
        if not 化合物批次:
            st.error("请先选择一份已确认化合物批次；毒理分析不能再直接手工定义化合物清单。")
            return
        _保存会话(管理器, 新会话)
        管理器.保存筛选结果("毒理人工证据", 编辑后证据)
        历史证据 = _读取(管理器, "毒理历史证据")
        本地证据 = pd.concat([编辑后证据, 历史证据], ignore_index=True) if not 历史证据.empty else 编辑后证据
        控制器 = 创建颅骨透明化筛选流程控制器(项目根目录)
        公开证据 = 控制器.执行毒理公开数据查询(新会话) if 启用PubChem else pd.DataFrame()
        本轮证据 = pd.concat([本地证据, 公开证据], ignore_index=True) if not 公开证据.empty else 本地证据
        结果 = 控制器.执行毒理证据匹配(新会话, 本轮证据)
        st.success(f"匹配完成：{len(结果['匹配结果'])} 条证据记录，{len(结果['数据缺口'])} 条数据缺口。")

    for 标题, 标识 in (("匹配结果", "毒理匹配结果"), ("PubChem GHS 危险提示", "毒理危险提示"), ("PubChem 查询日志", "毒理公开查询日志"), ("数据缺口", "毒理数据缺口"), ("公开数据源接口状态", "毒理来源接口状态"), ("分析摘要", "毒理分析摘要")):
        数据 = _读取(管理器, 标识)
        if not 数据.empty:
            st.subheader(标题)
            st.dataframe(数据, use_container_width=True, hide_index=True)

    with st.expander("保留的既有毒性结果接口", expanded=False):
        st.caption("以下是旧流程已生成的结果，仅保留展示接口，不会被新匹配逻辑删除或合并为风险分数。")
        for 标题, 标识 in (("既有毒性原始证据", "毒性原始证据"), ("既有动物实验模式", "当前动物实验模式结果"), ("既有人体口服模式", "未来人体口服模式结果"), ("既有终点字典", "毒性终点字典")):
            数据 = _读取(管理器, 标识)
            if not 数据.empty:
                st.markdown(f"**{标题}**")
                st.dataframe(数据, use_container_width=True, hide_index=True)
