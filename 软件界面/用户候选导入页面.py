"""通用候选导入：选择应用配置、逐条控制规则并展示 run_id 结果。"""

from pathlib import Path

import streamlit as st

from 核心系统.化合物确认清单 import 获取当前工作草稿, 保存工作草稿成分, 向工作草稿追加候选, 确认工作草稿, 可确认候选, 设置工作草稿用途配置
from 插件.颅骨透明化.颅骨透明化用途插件 import 成分角色选项
from 核心系统.流程控制器 import 创建颅骨透明化筛选流程控制器
from 核心系统.运行数据管理 import 运行数据管理器
from 核心系统.通用规则引擎 import 规则注册表
from 插件.数据导入.通用候选表导入插件 import 通用候选表导入插件


项目根目录 = Path(__file__).resolve().parents[1]


def 渲染用户候选导入页面() -> None:
    st.header("用户候选导入与配置化筛选")
    st.caption("仅支持 CSV/XLSX；每次运行生成独立 run_id，原始文件和全部结果均存入该运行目录。")
    上传 = st.file_uploader("选择候选表", type=["csv", "xlsx"])
    if 上传 is None:
        return
    内容 = 上传.getvalue()
    try:
        预览 = 通用候选表导入插件.读取上传内容(上传.name, 内容)
    except Exception as 错误:
        st.error(f"无法读取文件：{错误}")
        return
    st.subheader("字段映射预览")
    st.dataframe(预览.head(20), use_container_width=True, hide_index=True)
    选项 = ["不映射"] + list(预览.columns)
    候选类型 = st.radio("候选类型", ["水相候选（wRIMS）", "有机相候选（oRIMS）", "通用候选"], horizontal=True)
    名称列 = st.selectbox("化学名称列", 选项, index=1 if len(选项) > 1 else 0)
    CAS列 = st.selectbox("CAS列", 选项)
    货号列 = st.selectbox("货号列", 选项)
    编号列 = st.selectbox("用户候选编号列（不选则自动生成）", 选项)
    st.subheader("可选物化字段映射")
    可选 = {
        "水合能力平均值列": "水合评分平均值", "水合能力标准差列": "水合评分标准差", "eRI列": "eRI", "pH列": "预测pH",
        "dD列": "dD", "dP列": "dP", "dH列": "dH", "实测RI列": "实测RI", "气味列": "气味",
        "毒性或安全性列": "毒性或安全性", "实际互溶状态列": "实际互溶状态",
    }
    物化映射 = {键: (None if (列 := st.selectbox(标签, 选项, key=键)) == "不映射" else 列) for 键, 标签 in 可选.items()}
    注册表 = 规则注册表.默认()
    配置选项 = {配置.配置名称: 配置.配置编号 for 配置 in 注册表.配置列表()}
    st.subheader("应用配置与规则")
    配置名称 = st.selectbox("应用配置", list(配置选项))
    配置编号 = 配置选项[配置名称]
    规则启用覆盖 = {}
    for 规则 in 注册表.规则列表(配置编号):
        规则启用覆盖[规则.规则编号] = st.checkbox(
            f"{规则.规则编号}｜{规则.规则名称}（{规则.缺失数据策略}）",
            value=规则.是否启用,
            key=f"规则_{配置编号}_{规则.规则编号}",
        )
    st.caption("规则未启用时输出“跳过”；启用但属性缺失时输出“无法评估”，不会将缺失当作 0、通过或排除。")
    if st.button("保存并运行候选筛选", type="primary"):
        if 名称列 == "不映射":
            st.error("必须指定化学名称列")
            return
        映射 = {
            "化学名称列": 名称列,
            "CAS列": None if CAS列 == "不映射" else CAS列,
            "货号列": None if 货号列 == "不映射" else 货号列,
            "候选编号列": None if 编号列 == "不映射" else 编号列,
            **物化映射,
        }
        设置 = {"应用配置": 配置编号, "规则启用覆盖": 规则启用覆盖, "允许网络身份查询": False}
        try:
            with st.spinner("正在创建独立运行并执行身份、结构、属性与规则步骤…"):
                摘要 = 创建颅骨透明化筛选流程控制器(项目根目录).执行用户候选导入(上传.name, 内容, 映射, 设置, 候选类型, 配置编号)
            st.session_state["当前用户筛选run_id"] = 摘要["run_id"]
            st.success(f"运行完成：{摘要['run_id']}；规则通过 {摘要['规则通过数']}；无法评估 {摘要['无法评估数']}。")
            st.caption(f"报告：{摘要['报告路径']}")
        except Exception as 错误:
            st.error(f"运行失败：{错误}")
    run_id = st.session_state.get("当前用户筛选run_id")
    if run_id:
        管理器 = 运行数据管理器(项目根目录)
        try:
            管理器.激活运行(run_id)
            结果 = 管理器.读取筛选结果("用户导入_规则筛选结果")
            st.subheader(f"运行结果：{run_id}")
            st.dataframe(结果, use_container_width=True, hide_index=True)
            st.subheader("待确认化合物工作清单")
            st.caption("用途在工作清单开始时确定；后续可连续追加化合物并继承设置。只有最后确认才会冻结正式历史批次。")
            草稿元数据, 草稿成分 = 获取当前工作草稿(管理器)
            st.selectbox("本工作清单用途", ["颅骨透明化"], disabled=True, key=f"用途_{草稿元数据['草稿编号']}")
            左, 中, 右 = st.columns(3)
            目标RI = 左.number_input("目标折射率 RI", min_value=1.0, max_value=2.0, value=float(草稿元数据.get("目标折射率", 1.56)), step=0.001, format="%.3f", key=f"目标RI_{草稿元数据['草稿编号']}")
            温度 = 中.number_input("评估温度（°C）", value=float(草稿元数据.get("温度_C", 25.0)), step=1.0, key=f"温度_{草稿元数据['草稿编号']}")
            HSP参照 = 右.text_input("HSP参照体系", value=str(草稿元数据.get("HSP参照体系", "AqIS；oRIMS")), key=f"HSP参照_{草稿元数据['草稿编号']}")
            if st.button("保存颅骨透明化用途配置", key=f"保存用途_{草稿元数据['草稿编号']}"):
                草稿元数据 = 设置工作草稿用途配置(管理器, str(草稿元数据["草稿编号"]), {"目标折射率": 目标RI, "温度_C": 温度, "HSP参照体系": HSP参照})
                st.success("已保存用途配置；后续新增成分会继承该设置。")
            候选 = 可确认候选(管理器, run_id)
            默认候选 = 候选.loc[候选.get("规则总状态", "").eq("通过"), "候选编号"].astype(str).tolist() if "规则总状态" in 候选 else []
            待加入候选 = st.multiselect("选择加入当前工作清单的化合物", 候选["候选编号"].astype(str).tolist(), default=默认候选, key=f"加入候选_{run_id}")
            if st.button("加入待确认工作清单", key=f"加入草稿_{run_id}"):
                草稿元数据, 草稿成分 = 向工作草稿追加候选(管理器, run_id, 待加入候选)
                st.success(f"已加入草稿 {草稿元数据['草稿编号']}，当前共 {len(草稿成分)} 个成分；可继续运行下一轮候选选择后再追加。")
            草稿元数据, 草稿成分 = 获取当前工作草稿(管理器)
            if 草稿成分.empty:
                st.info("当前工作清单为空。选中上方候选后加入即可；之后可直接继续下一轮化合物选择。")
            else:
                st.caption("此表是唯一的成分录入处：颅骨专用物性、功能步骤和浓度都在同一成分行维护；最终确认后只自动计算，不再要求重录化合物。")
                显示列 = [
                    "来源运行编号", "候选编号", "化学名称", "CAS", "浓度值", "浓度单位", "颅骨透明化角色",
                    "纯物质RI", "eRI", "浓度下RI", "实验水合评分", "HSP_dD", "HSP_dP", "HSP_dH",
                    "水中溶解度", "BA中溶解度", "VA中溶解度", "AqIS中溶解度", "预测混溶性", "实验混溶性",
                    "沉淀", "浑浊", "分层", "分层时间", "颜色", "颜色变化", "吸收峰_nm", "pH",
                    "脱钙证据", "脱脂证据", "胶原处理证据", "数据来源", "是否纳入颅骨透明化计算", "颅骨透明化用途状态",
                ]
                可编辑 = 草稿成分[[列 for 列 in 显示列 if 列 in 草稿成分]].copy()
                编辑后 = st.data_editor(可编辑, use_container_width=True, hide_index=True, key=f"草稿成分_{草稿元数据['草稿编号']}", column_config={"颅骨透明化角色": st.column_config.SelectboxColumn(options=list(成分角色选项))})
                if st.button("更新工作清单", key=f"保存草稿_{草稿元数据['草稿编号']}"):
                    键 = ["来源运行编号", "候选编号"]
                    更新列 = [列 for 列 in 显示列 if 列 in 编辑后 and 列 not in {"来源运行编号", "候选编号", "化学名称", "CAS", "颅骨透明化用途状态"}]
                    更新索引 = 编辑后.set_index(键)
                    完整 = 草稿成分.copy().set_index(键)
                    for 列 in 更新列:
                        完整.loc[更新索引.index, 列] = 更新索引[列]
                    保存工作草稿成分(管理器, str(草稿元数据["草稿编号"]), 完整.reset_index())
                    st.success("已更新工作草稿；尚未产生正式历史批次。")
                清单名称 = st.text_input("最终确认清单名称", value="本轮化合物确认清单", key=f"最终清单名称_{草稿元数据['草稿编号']}")
                确认备注 = st.text_area("最终确认备注", key=f"最终确认备注_{草稿元数据['草稿编号']}")
                if st.button("确认完整清单并生成正式批次", type="primary", key=f"最终确认_{草稿元数据['草稿编号']}"):
                    元数据, 清单 = 确认工作草稿(管理器, str(草稿元数据["草稿编号"]), 清单名称, "颅骨透明化", 确认备注)
                    st.success(f"已确认 {len(清单)} 个成分，生成正式批次 {元数据['批次编号']}；已自动生成 {元数据.get('描述符记录数', 0)} 条通用描述符并完成颅骨配方聚合。")
        except FileNotFoundError:
            st.info("当前运行尚未生成筛选结果。")
