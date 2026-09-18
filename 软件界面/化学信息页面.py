"""展示真实结构映射、RDKit 描述符和 Hansen 距离。"""

from pathlib import Path

import streamlit as st

from 核心系统.数据管理接口 import 文件数据访问管理器


项目根目录 = Path(__file__).resolve().parents[1]


def 渲染化学信息页面() -> None:
    st.header("化学信息")
    数据管理器 = 文件数据访问管理器(项目根目录)
    if not 数据管理器.结果存在("补充数据3_化学属性统一记录", 是否最终结果=True):
        st.warning("请先在“候选试剂”页面运行补充数据3真实处理流程。")
        return
    统一记录 = 数据管理器.读取最终结果("补充数据3_化学属性统一记录")
    描述符表 = 数据管理器.读取中间结果("补充数据3_RDKit描述符结果")
    汉森表 = 数据管理器.读取中间结果("补充数据3_汉森距离结果")
    候选编号 = st.selectbox("选择试剂", 统一记录["候选编号"].tolist())
    当前记录 = 统一记录.loc[统一记录["候选编号"].eq(候选编号)].iloc[0]
    st.subheader(f"{当前记录['论文_化学名称']}（{候选编号}）")
    列1, 列2 = st.columns(2)
    with 列1:
        st.markdown("#### 论文原始属性")
        st.dataframe(
            当前记录[["论文_CAS号", "论文_eRI原始", "论文_dD", "论文_dP", "论文_dH", "论文_与BA混合折射率", "论文_与VA混合折射率"]].to_frame("数值"),
            use_container_width=True,
        )
    with 列2:
        st.markdown("#### 分子结构状态")
        st.dataframe(
            当前记录[["结构状态", "结构映射_SMILES", "结构映射_PubChemCID", "结构映射_来源URL", "结构映射_人工核对状态", "结构错误信息"]].to_frame("数值"),
            use_container_width=True,
        )
    st.markdown("#### RDKit 描述符")
    st.dataframe(描述符表.loc[描述符表["候选编号"].eq(候选编号)], use_container_width=True, hide_index=True)
    st.markdown("#### Hansen 距离")
    距离结果 = 汉森表.loc[汉森表["候选编号"].eq(候选编号)]
    if 距离结果.empty:
        st.info("该试剂是 BA 或 VA 参照试剂；本阶段不计算其对自身的距离。")
    else:
        st.dataframe(距离结果, use_container_width=True, hide_index=True)
    st.markdown("#### 缺失与错误")
    st.dataframe(当前记录[["缺失状态", "错误信息"]].to_frame("信息"), use_container_width=True)
