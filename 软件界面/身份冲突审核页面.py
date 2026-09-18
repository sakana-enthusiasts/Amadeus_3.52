"""人工处理不确定CID、盐/水合物或手工结构的审核页面。"""

from pathlib import Path
import streamlit as st

from 核心系统.数据管理接口 import 文件数据访问管理器
from 插件.数据导入.人工身份确认插件 import 人工身份确认插件

项目根目录 = Path(__file__).resolve().parents[1]


def 渲染身份冲突审核页面() -> None:
    st.header("化合物身份冲突审核")
    管理器 = 文件数据访问管理器(项目根目录)
    try:
        冲突 = 管理器.读取筛选结果("化合物身份冲突表")
    except FileNotFoundError:
        st.info("尚未生成身份冲突记录。请先运行候选导入或规则筛选。")
        return
    if 冲突.empty:
        st.info("当前无记录。")
        return
    st.dataframe(冲突, use_container_width=True, hide_index=True)
    候选编号 = st.selectbox("选择待审核候选", sorted(冲突["候选编号"].astype(str).unique()))
    操作 = st.radio("审核决定", ["确认CID", "标记无法确认", "手工输入结构"], horizontal=True)
    CID = st.text_input("确认的PubChem CID（仅确认CID时必填）")
    SMILES = st.text_area("人工确认的SMILES（仅手工输入结构时必填）")
    说明 = st.text_area("审核说明／依据")
    if st.button("保存人工确认", type="primary"):
        try:
            人工身份确认插件().执行({"数据管理器": 管理器, "候选编号": 候选编号, "操作": 操作, "PubChem CID": CID, "Isomeric SMILES": SMILES, "说明": 说明})
            st.success("人工确认已保存到软件数据库；后续身份转换会优先复用。")
            st.rerun()
        except Exception as 错误:
            st.error(f"未保存：{错误}")
