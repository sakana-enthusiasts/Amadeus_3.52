"""真实补充数据2筛选结果、结构分析、冲突审计与导出页面。"""

from pathlib import Path

import pandas as pd
import streamlit as st

from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.流程控制器 import 创建颅骨透明化筛选流程控制器
from 核心系统.通用规则引擎 import 规则注册表
from 设置.插件启用设置 import 启用结果可视化
from 软件界面.结果可视化组件 import 渲染候选散点图, 渲染筛选过程图

项目根目录 = Path(__file__).resolve().parents[1]
结果标识 = "补充数据2_规则筛选统一记录"


def _读取(数据管理器: 文件数据访问管理器, 方法: str, 标识: str) -> pd.DataFrame:
    try:
        return getattr(数据管理器, 方法)(标识)
    except FileNotFoundError:
        return pd.DataFrame()


def 渲染规则筛选页面() -> None:
    st.header("规则筛选")
    st.caption("用户候选流程使用“应用配置＋可选规则”；论文复现流程仅用于对照，不会读取最终10标签参与筛选。")
    with st.expander("应用配置与毒性规则注册表", expanded=False):
        注册表 = 规则注册表.默认()
        for 配置 in 注册表.配置列表():
            st.markdown(f"**{配置.配置名称}**：{配置.说明}")
            规则表 = 注册表.导出规则(配置.配置编号)
            st.dataframe(规则表, use_container_width=True, hide_index=True)
    数据管理器 = 文件数据访问管理器(项目根目录)
    if st.button("重新运行完整筛选", type="primary", help="重读补充数据2，复用本地PubChem结构缓存，覆盖本次筛选结果；不修改论文原始文件。"):
        with st.spinner("正在执行真实数值筛选、结构解析、RDKit、距离、冲突审计和报告……"):
            st.session_state["规则筛选运行摘要"] = 创建颅骨透明化筛选流程控制器(项目根目录).执行补充数据2规则筛选流程()
        st.success("已重新生成筛选结果与Excel报告。")
    if not 数据管理器.结果存在(结果标识, 是否最终结果=True):
        st.info("尚未生成补充数据2真实筛选结果，请点击“重新运行完整筛选”。")
        return
    记录 = 数据管理器.读取筛选结果(结果标识) if (数据管理器.筛选结果目录 / f"{结果标识}.csv").is_file() else 数据管理器.读取最终结果(结果标识)
    图表目录 = 数据管理器.导出结果目录 / "图表"
    if 启用结果可视化() and st.button("重新生成图表", help="读取当前筛选统计和自动候选，覆盖本项目导出结果目录中的图表。"):
        创建颅骨透明化筛选流程控制器(项目根目录).插件管理器.获取插件("筛选结果图表").执行({"数据管理器": 数据管理器})
        st.success("已按当前筛选结果重新生成PNG和SVG图表。")
    elif not 启用结果可视化():
        st.caption("结果图表已由配置临时关闭；筛选与报告导出仍可正常使用。")
    步骤 = _读取(数据管理器, "读取中间结果", "补充数据2_规则筛选步骤统计")
    结构 = _读取(数据管理器, "读取中间结果", "补充数据2_结构映射结果")
    冲突 = _读取(数据管理器, "读取筛选结果", "补充数据2与3_官方数据冲突记录")
    自动 = 记录[记录["自动规则通过"].astype(str).str.lower().eq("true")]
    最终10 = 自动[自动["论文最终10候选标签"].eq("是")]
    额外10 = 自动[~自动["论文最终10候选标签"].eq("是")]
    列 = st.columns(5)
    for 位置, 标签, 数值 in zip(列, ["清理后真实候选", "eRI后结构分析", "自动数值候选", "论文最终10恢复", "官方冲突字段"], [len(记录), len(结构), len(自动), f"{len(最终10)}/10", len(冲突)]):
        位置.metric(标签, 数值)
    st.caption("原始文件：SeeThrough补充数据2_1619个水相候选.xlsx；页面结果由共用数据管理层读取。运行时间见下载报告的“运行摘要”。")
    st.subheader("软件真实计算流程")
    st.dataframe(步骤, use_container_width=True, hide_index=True)
    if 启用结果可视化():
        st.caption("交互式概览：悬停查看每步的候选数量。")
        渲染筛选过程图(步骤)
    st.subheader("筛选数量变化图")
    数量PNG, 数量SVG = 图表目录 / "候选试剂筛选数量变化图.png", 图表目录 / "候选试剂筛选数量变化图.svg"
    if 数量PNG.is_file():
        st.image(str(数量PNG), caption="SeeThrough候选试剂自动筛选结果", use_container_width=True)
        下载列1, 下载列2 = st.columns(2)
        下载列1.download_button("下载数量变化图 PNG（300 DPI）", 数量PNG.read_bytes(), 数量PNG.name, "image/png")
        下载列2.download_button("下载数量变化图 SVG", 数量SVG.read_bytes(), 数量SVG.name, "image/svg+xml", disabled=not 数量SVG.is_file())
    else:
        st.warning("尚未生成图表，请点击“重新生成图表”或重跑完整筛选。")
    st.subheader("最终候选分布图")
    分布PNG, 分布SVG = 图表目录 / "最终候选物化参数分布图.png", 图表目录 / "最终候选物化参数分布图.svg"
    if 分布PNG.is_file():
        st.image(str(分布PNG), caption="自动筛选候选的物化参数分布", use_container_width=True)
        下载列1, 下载列2 = st.columns(2)
        下载列1.download_button("下载候选分布图 PNG（300 DPI）", 分布PNG.read_bytes(), 分布PNG.name, "image/png")
        下载列2.download_button("下载候选分布图 SVG", 分布SVG.read_bytes(), 分布SVG.name, "image/svg+xml", disabled=not 分布SVG.is_file())
    if 启用结果可视化():
        st.caption("交互式候选概览：可缩放、平移，并悬停查看候选信息。")
        渲染候选散点图(自动)
    st.subheader("当前规则与阈值")
    st.table(pd.DataFrame({"规则": ["必要字段", "水合评分", "水合能力", "eRI", "Hansen距离"], "阈值": ["水合能力、eRI、dD/dP/dH完整", ">= -1.5", "> BA", "> 1.58", "Ra(BA) < 10"]}))
    st.subheader("论文方法对照（不计入软件自动统计）")
    st.info("论文报告约140个芳香候选；当前补充数据未公开该140个候选的完整成员ID，软件尚未独立恢复该集合。RDKit的“是否含芳香环”仅作为结构分析，不作为自动排除条件。论文最终10仅在自动筛选完成后用于对照。")
    st.subheader("20个最终自动候选")
    显示 = st.radio("候选查看", ["全部20个", "论文最终10", "自动额外10个"], horizontal=True)
    展示表 = 自动 if 显示 == "全部20个" else (最终10 if 显示 == "论文最终10" else 额外10)
    展示列 = [列名 for 列名 in ["候选编号", "论文_化学名称", "论文_水合能力平均值", "论文_eRI", "汉森距离_与BA", "汉森距离_与VA", "结构状态", "芳香性", "芳香环数量", "基础官能团", "论文最终10对照状态", "人工有害性标签", "人工毒性标签", "人工气味标签", "人工稳定性标签", "人工变色标签", "标签来源", "额外候选处理建议"] if 列名 in 展示表.columns]
    st.dataframe(展示表[展示列], use_container_width=True, hide_index=True)
    st.subheader("41个候选的结构解析与RDKit结果")
    结构列 = [列名 for 列名 in ["候选编号", "论文_化学名称", "论文_CAS号", "结构状态", "结构映射_PubChemCID", "结构映射_名称核对状态", "结构错误信息"] if 列名 in 结构.columns]
    st.dataframe(结构[结构列], use_container_width=True, hide_index=True)
    st.subheader("官方补充数据冲突记录")
    st.dataframe(冲突 if not 冲突.empty else pd.DataFrame({"说明": ["未发现共同字段差异"]}), use_container_width=True, hide_index=True)
    st.subheader("逐候选审计")
    范围 = st.selectbox("审计范围", ["全部1619个候选", "自动排除候选", "自动额外10个候选"])
    审计 = 记录 if 范围 == "全部1619个候选" else (记录[~记录["自动规则通过"].astype(str).str.lower().eq("true")] if 范围 == "自动排除候选" else 额外10)
    st.dataframe(审计, use_container_width=True, hide_index=True, height=380)
    报告路径 = 数据管理器.导出结果目录 / "SeeThrough规则筛选演示报告.xlsx"
    if 报告路径.is_file():
        st.download_button("下载完整筛选报告", data=报告路径.read_bytes(), file_name=报告路径.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
