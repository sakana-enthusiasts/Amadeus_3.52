from pathlib import Path

import pandas as pd
import streamlit as st

from 核心系统.化合物确认清单 import 已确认清单目录
from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.颅骨透明化用途 import 配方特征标识
from 插件.颅骨透明化.颅骨透明化用途插件 import 用途标识


项目根目录 = Path(__file__).resolve().parents[1]


def 渲染实验优化页面() -> None:
    st.header("实验优化")
    if not hasattr(st, "selectbox"):
        st.info("展示颅骨透明化实验优化接口的输入就绪状态。")
        return
    管理器 = 文件数据访问管理器(项目根目录)
    目录 = 已确认清单目录(管理器)
    目录 = 目录.loc[目录.get("用途标识", pd.Series(dtype=str)).astype(str).eq(用途标识)] if not 目录.empty and "用途标识" in 目录 else pd.DataFrame()
    if 目录.empty:
        st.info("尚无颅骨透明化确认批次。")
        return
    批次编号 = st.selectbox("选择批次", 目录["批次编号"].astype(str).tolist())
    try:
        特征 = 管理器.读取软件数据库表格(配方特征标识)
        特征 = 特征.loc[特征["批次编号"].astype(str).eq(批次编号)]
    except FileNotFoundError:
        特征 = pd.DataFrame()
    if 特征.empty:
        st.info("请先完成配方用途评估并录入至少一个实验终点。")
    else:
        状态 = str(特征.iloc[-1].get("优化器输入状态", "待补实验终点"))
        st.info(f"实验优化接口状态：{状态}。当前不在缺少实验数据时生成下一轮实验建议。")
