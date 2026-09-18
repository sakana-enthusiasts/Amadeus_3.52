"""最小本地软件界面；只负责页面导航，不承载业务算法。"""

import streamlit as st

from 软件界面.候选试剂页面 import 渲染候选试剂页面
from 软件界面.化学信息页面 import 渲染化学信息页面
from 软件界面.规则筛选页面 import 渲染规则筛选页面
from 软件界面.配方构建页面 import 渲染配方构建页面
from 软件界面.配方研发页面 import 渲染配方研发页面
from 软件界面.透明化预测页面 import 渲染透明化预测页面
from 软件界面.实验记录页面 import 渲染实验记录页面
from 软件界面.实验优化页面 import 渲染实验优化页面
from 软件界面.用户候选导入页面 import 渲染用户候选导入页面
from 软件界面.毒性评估页面 import 渲染毒性评估页面
from 软件界面.身份冲突审核页面 import 渲染身份冲突审核页面


页面映射 = {
    "候选试剂": 渲染候选试剂页面,
    "用户候选导入": 渲染用户候选导入页面,
    "身份冲突审核": 渲染身份冲突审核页面,
    "化学信息": 渲染化学信息页面,
    "规则筛选": 渲染规则筛选页面,
    "配方构建": 渲染配方构建页面,
    "配方发现与验证": 渲染配方研发页面,
    "透明化预测": 渲染透明化预测页面,
    "实验记录": 渲染实验记录页面,
    "实验优化": 渲染实验优化页面,
    "毒性评估": 渲染毒性评估页面,
}


def 运行主界面() -> None:
    """运行 Amadeus 的本地演示界面。"""
    st.set_page_config(page_title="Amadeus · Automated Screening Framework", page_icon="⚗️", layout="wide")
    st.title("Amadeus")
    st.caption("Automated Screening Framework · Demo 2.0")
    st.info("用于颅骨透明化试剂候选筛选、化学信息核验、结果可视化与报告导出。预测页面只展示已具备训练依据的结果，不生成虚构预测。")
    当前页面 = st.sidebar.radio("功能入口", list(页面映射))
    st.sidebar.divider()
    st.sidebar.caption("Amadeus Demo 2.0\n\n核心算法与结果可视化分层；可视化可按配置临时关闭。")
    页面映射[当前页面]()
