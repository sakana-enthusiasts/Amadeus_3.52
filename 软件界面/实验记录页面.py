from pathlib import Path

import pandas as pd
import streamlit as st

from 核心系统.化合物确认清单 import 已确认清单目录
from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.颅骨透明化用途 import 保存实验记录, 读取实验记录
from 插件.颅骨透明化.颅骨透明化用途插件 import 实验终点字段, 用途标识


项目根目录 = Path(__file__).resolve().parents[1]


def 渲染实验记录页面() -> None:
    st.header("实验记录")
    if not hasattr(st, "selectbox"):
        st.info("记录颅骨透明化实验终点；实验值只作为真实标签保存。")
        return
    管理器 = 文件数据访问管理器(项目根目录)
    目录 = 已确认清单目录(管理器)
    目录 = 目录.loc[目录.get("用途标识", pd.Series(dtype=str)).astype(str).eq(用途标识)] if not 目录.empty and "用途标识" in 目录 else pd.DataFrame()
    if 目录.empty:
        st.info("尚无颅骨透明化确认批次。")
        return
    批次编号 = st.selectbox("选择批次", 目录["批次编号"].astype(str).tolist())
    记录 = 读取实验记录(管理器, 批次编号).drop(columns=["批次编号"], errors="ignore")
    if 记录.empty:
        记录 = pd.DataFrame([{ "终点": "透射率", "数值": pd.NA, "单位": "%", "数据来源": "", "备注": "" }])
    编辑后 = st.data_editor(记录, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"实验终点_{批次编号}", column_config={"终点": st.column_config.SelectboxColumn(options=list(实验终点字段))})
    if st.button("保存实验终点", type="primary", key=f"保存实验终点_{批次编号}"):
        保存实验记录(管理器, 批次编号, 编辑后)
        st.success("已保存实验终点。它们不会被折算成单一透明化分数。")
