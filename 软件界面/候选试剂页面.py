"""展示经共用数据管理层读取的补充数据3真实候选结果。"""

from pathlib import Path

import streamlit as st

from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.流程控制器 import 创建补充数据3流程控制器


项目根目录 = Path(__file__).resolve().parents[1]
最终结果标识 = "补充数据3_化学属性统一记录"


def _获取统一记录():
    数据管理器 = 文件数据访问管理器(项目根目录)
    if not 数据管理器.结果存在(最终结果标识, 是否最终结果=True):
        st.warning("尚未生成补充数据3处理结果。")
        if st.button("导入并处理补充数据3", type="primary"):
            创建补充数据3流程控制器(项目根目录).执行补充数据3真实流程()
            st.rerun()
        return None
    return 数据管理器.读取最终结果(最终结果标识)


def 渲染候选试剂页面() -> None:
    st.header("候选试剂")
    统一记录 = _获取统一记录()
    if 统一记录 is None:
        return
    st.caption("数据来自 SeeThrough Supplementary Data 3；页面仅读取共用数据管理层生成的统一记录。")
    水相候选数 = int(统一记录["试剂角色"].eq("水相候选").sum())
    结构成功数 = int(统一记录["结构状态"].eq("已获得").sum())
    列1, 列2, 列3 = st.columns(3)
    列1.metric("导入试剂数量", len(统一记录))
    列2.metric("水相候选数量", 水相候选数)
    列3.metric("成功获得结构", f"{结构成功数}/{len(统一记录)}")
    展示列 = [
        "候选编号", "试剂角色", "论文_化学名称", "论文_CAS号", "论文_eRI原始",
        "论文_dD", "论文_dP", "论文_dH", "论文_与BA混合折射率", "论文_与VA混合折射率",
        "结构状态", "汉森距离_与BA", "汉森距离_与VA", "缺失状态", "错误信息",
    ]
    st.dataframe(统一记录[展示列], use_container_width=True, hide_index=True)
