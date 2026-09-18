"""结果页面共用的轻量可视化组件。

组件只消费已经由核心流程生成的数据；当字段不足时保持页面可用并给出
说明，而不是把图形展示错误扩散到筛选流程。
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st


def 渲染筛选过程图(步骤统计: pd.DataFrame) -> None:
    """展示每一步保留的候选数量。"""
    必需列 = {"筛选步骤", "剩余数量"}
    if 步骤统计.empty or not 必需列.issubset(步骤统计.columns):
        st.info("当前运行没有可用于绘图的筛选步骤统计。")
        return

    数据 = 步骤统计[["筛选步骤", "剩余数量"]].copy()
    数据["剩余数量"] = pd.to_numeric(数据["剩余数量"], errors="coerce")
    数据 = 数据.dropna(subset=["剩余数量"])
    if 数据.empty:
        st.info("筛选步骤统计中的数量不是可绘制的数值。")
        return

    图 = (
        alt.Chart(数据)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color="#2A6F97")
        .encode(
            x=alt.X("筛选步骤:N", sort=None, title=None, axis=alt.Axis(labelAngle=-20, labelLimit=150)),
            y=alt.Y("剩余数量:Q", title="剩余候选数量"),
            tooltip=[alt.Tooltip("筛选步骤:N", title="步骤"), alt.Tooltip("剩余数量:Q", title="候选数量", format=",")],
        )
        .properties(height=310)
    )
    st.altair_chart(图, use_container_width=True)


def 渲染候选散点图(候选: pd.DataFrame) -> None:
    """展示自动候选的 Hansen 距离与估算折射率分布。"""
    必需列 = {"汉森距离_与BA", "论文_eRI"}
    if 候选.empty or not 必需列.issubset(候选.columns):
        st.info("当前结果缺少 Hansen 距离或 eRI 字段，暂不展示候选散点图。")
        return

    数据 = 候选.copy()
    for 列 in 必需列:
        数据[列] = pd.to_numeric(数据[列], errors="coerce")
    数据 = 数据.dropna(subset=list(必需列))
    if 数据.empty:
        st.info("当前自动候选没有同时具备可绘制的 Hansen 距离和 eRI。")
        return

    标签列 = "论文最终10候选标签"
    数据["候选类别"] = (
        数据[标签列].eq("是").map({True: "论文最终10（对照）", False: "自动额外候选"})
        if 标签列 in 数据.columns
        else "自动候选"
    )
    提示字段 = [
        alt.Tooltip("候选类别:N", title="类别"),
        alt.Tooltip("汉森距离_与BA:Q", title="Ra(BA)", format=".3f"),
        alt.Tooltip("论文_eRI:Q", title="eRI", format=".4f"),
    ]
    if "论文_化学名称" in 数据.columns:
        提示字段.insert(0, alt.Tooltip("论文_化学名称:N", title="化学名称"))
    图 = (
        alt.Chart(数据)
        .mark_circle(size=100, opacity=0.82)
        .encode(
            x=alt.X("汉森距离_与BA:Q", title="与 BA 的 Hansen 距离 Ra"),
            y=alt.Y("论文_eRI:Q", title="估算折射率 eRI"),
            color=alt.Color("候选类别:N", title=None, scale=alt.Scale(range=["#D05A4E", "#4F8FB3"])),
            tooltip=提示字段,
        )
        .interactive()
        .properties(height=360)
    )
    st.altair_chart(图, use_container_width=True)
