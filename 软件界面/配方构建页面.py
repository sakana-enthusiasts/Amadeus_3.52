from pathlib import Path

import pandas as pd
import streamlit as st

from 核心系统.化合物确认清单 import 已确认清单目录, 读取确认清单
from 核心系统.数据管理接口 import 文件数据访问管理器
from 核心系统.颅骨透明化用途 import 保存HSP参照, 保存成分证据, 保存配方设置, 读取HSP参照, 读取成分证据, 读取配方设置, 运行用途评估, 读取确认批次描述符
from 核心系统.配方评估流程 import _配置对象
from 插件.配方物性.配方物性汇总 import 创建默认模型注册表
from 设置.配方物性设置 import 默认物性模型, 实测字段
from 插件.颅骨透明化.颅骨透明化用途插件 import 用途标识


项目根目录 = Path(__file__).resolve().parents[1]


def _显示值(值) -> str:
    return "" if 值 is None or pd.isna(值) else str(值)


def _物性录入(管理器, 批次编号, 成分, 设置, 元数据) -> None:
    with st.expander("配方物性预测：选择模型与补充数据"):
        st.caption("默认仅使用实测数据。启用预测后，仍优先采用实测值；auto 会根据数据完整性选择可用模型。")
        st.caption("体积分数、摩尔分数各自总和须为 1，并包含溶剂；裸 % 不代表已明确比例基准。物性输入应对应同一温度。")
        列 = ["成分键", "化学名称", "体积分数", "摩尔分数", "纯物质RI", "纯物质黏度_mPa_s", "渗透角色", "摩尔浓度_mol_L", "范特霍夫因子", "数据来源"]
        编辑 = st.data_editor(成分.reindex(columns=列), disabled=["成分键", "化学名称"], hide_index=True,
                            use_container_width=True, key=f"物性成分_{批次编号}")
        注册表 = 创建默认模型注册表()
        try:
            选择 = 默认物性模型 | _配置对象(设置.get("物性模型选择"))
            条件 = _配置对象(设置.get("物性条件"))
            参数 = _配置对象(设置.get("物性模型参数"))
        except (ValueError, TypeError) as 错误:
            st.error(f"已存物性设置无效：{错误}")
            return
        标签 = {"measured_only": "仅实测", "auto": "自动选择", "lorentz_lorenz": "Lorentz–Lorenz",
              "ideal_log": "理想对数混合", "grunberg_nissan": "Grunberg–Nissan", "stokes_einstein": "Stokes–Einstein（自由扩散）",
              "ideal_osmotic": "理想渗透压", "osmotic_coefficient": "渗透系数修正", "ideal_water_activity": "理想水活度",
              "water_activity_coefficient": "水活度系数修正"}
        新实测 = {}
        for 指标 in 注册表.指标列表():
            左, 右 = st.columns(2)
            方法们 = 注册表.方法列表(指标)
            if 选择[指标] not in 方法们:
                st.error(f"已存模型不可用：{指标}/{选择[指标]}，请重新选择。")
            选择[指标] = 左.selectbox(f"{指标}模型", 方法们, index=方法们.index(选择[指标]) if 选择[指标] in 方法们 else 0,
                                    format_func=lambda x: 标签.get(x, x), key=f"物性方法_{指标}_{批次编号}")
            if 指标 != "混合折射率":  # RI 沿用上方已有录入框。
                单位 = 注册表.模型列表(指标)[0].单位
                新实测[实测字段[指标]] = 右.text_input(f"实测{指标} {单位}", value=_显示值(设置.get(实测字段[指标])), key=f"物性实测_{指标}_{批次编号}")
        温度 = st.text_input("物性计算温度（°C）", value=_显示值(条件.get("温度_C", 元数据.get("温度_C", 25))), key=f"物性温度_{批次编号}")
        半径 = st.text_input("扩散探针水动力半径（nm）", value=_显示值(条件.get("探针水动力半径_nm")), key=f"物性半径_{批次编号}")
        水键 = st.text_input("水成分键（与上表对应）", value=_显示值(条件.get("水成分键")), key=f"物性水键_{批次编号}")
        来源 = st.text_input("配方实测数据来源", value=_显示值(设置.get("物性实测来源")), key=f"物性来源_{批次编号}")
        st.caption("可选校准参数：无数据时留空；auto 会回退并在结果中说明原因。")
        系数 = st.text_input("当前配方的有效渗透系数", value=_显示值(参数.get("osmotic_coefficient", {}).get("渗透系数")), key=f"渗透系数_{批次编号}")
        水系数 = st.text_input("当前配方的水活度系数", value=_显示值(参数.get("water_activity_coefficient", {}).get("水活度系数")), key=f"水系数_{批次编号}")
        GN = 参数.get("grunberg_nissan", {})
        G行 = [{"成分键1": a, "成分键2": b, "Gij": g} for a, 行 in GN.get("Gij", {}).items() for b, g in 行.items()]
        st.caption("Grunberg–Nissan：填写所有非零组分对的 Gij；参数温度应与计算温度相同。")
        G编辑 = st.data_editor(pd.DataFrame(G行, columns=["成分键1", "成分键2", "Gij"]), num_rows="dynamic", key=f"Gij_{批次编号}")
        G温度 = st.text_input("Gij 校准温度（°C）", value=_显示值(GN.get("温度_C")), key=f"G温度_{批次编号}")
        if st.button("保存物性数据与模型选择", key=f"保存物性_{批次编号}"):
            新成分 = 成分.set_index("成分键")
            for 字段 in 列[2:]:
                新成分[字段] = 编辑.set_index("成分键")[字段]
            Gij = {}
            for _, 行 in G编辑.iterrows():
                a, b = sorted((_显示值(行["成分键1"]), _显示值(行["成分键2"])))
                if a and b:
                    Gij.setdefault(a, {})[b] = _显示值(行["Gij"])
            参数.update({"osmotic_coefficient": {"渗透系数": 系数}, "water_activity_coefficient": {"水活度系数": 水系数},
                        "grunberg_nissan": {"温度_C": G温度, "Gij": Gij}})
            保存成分证据(管理器, 批次编号, 新成分.reset_index())
            保存配方设置(管理器, 批次编号, 设置 | 新实测 | {"物性模型选择": 选择, "物性模型参数": 参数,
                "物性实测来源": 来源, "物性条件": 条件 | {"温度_C": 温度, "探针水动力半径_nm": 半径, "水成分键": 水键}})
            st.success("物性数据和模型选择已保存；运行用途评估可查看结果与缺失项。")


def 渲染配方构建页面() -> None:
    st.header("配方构建")
    if not hasattr(st, "selectbox"):  # 保持最小页面接口在无 Streamlit 环境可测试。
        st.info("颅骨透明化配方数据录入与用途评估入口。")
        return
    管理器 = 文件数据访问管理器(项目根目录)
    目录 = 已确认清单目录(管理器)
    目录 = 目录.loc[目录.get("用途标识", pd.Series(dtype=str)).astype(str).eq(用途标识)] if not 目录.empty and "用途标识" in 目录 else pd.DataFrame()
    if 目录.empty:
        st.info("尚无已确认的颅骨透明化批次。请先在“用户候选导入”确认完整化合物清单。")
        return
    显示 = {f"{行['批次编号']}｜{行.get('清单名称', '')}": str(行["批次编号"]) for _, 行 in 目录.iterrows()}
    批次编号 = st.selectbox("选择颅骨透明化批次", list(显示.values()), format_func=lambda 值: next(标签 for 标签, 编号 in 显示.items() if 编号 == 值))
    元数据, 清单 = 读取确认清单(管理器, 批次编号)
    st.caption(f"目标 RI：{元数据.get('目标折射率', 1.56)}；用途配置版本：{元数据.get('用途配置版本', '1.0')}。成分数据来自已确认工作清单，此页不要求重新录入。")

    成分证据 = 读取成分证据(管理器, 批次编号, 清单)
    st.subheader("已确认的成分与颅骨专用字段")
    st.dataframe(成分证据, use_container_width=True, hide_index=True)
    描述符 = 读取确认批次描述符(管理器, 批次编号)
    st.caption(f"确认后已生成 {len(描述符)} 条通用化学描述符；配方评估会自动将其与此清单聚合。")

    st.subheader("HSP 参照体系")
    HSP参照 = 读取HSP参照(管理器, 批次编号)
    if HSP参照.empty:
        HSP参照 = pd.DataFrame([{"参照体系": "AqIS", "HSP_dD": pd.NA, "HSP_dP": pd.NA, "HSP_dH": pd.NA, "数据来源": ""}, {"参照体系": "oRIMS", "HSP_dD": pd.NA, "HSP_dP": pd.NA, "HSP_dH": pd.NA, "数据来源": ""}])
    HSP编辑后 = st.data_editor(HSP参照.drop(columns=["批次编号"], errors="ignore"), num_rows="dynamic", use_container_width=True, hide_index=True, key=f"HSP参照_{批次编号}")
    if st.button("保存 HSP 参照", key=f"保存HSP_{批次编号}"):
        保存HSP参照(管理器, 批次编号, HSP编辑后)
        st.success("已保存 HSP 参照；仅在候选和参照的 dD/dP/dH 均完整时计算 Ra。")

    st.subheader("配方层实验/观察数据")
    设置 = 读取配方设置(管理器, 批次编号)
    左, 中, 右 = st.columns(3)
    混合RI = 左.text_input("混合液实测 RI", value=str(设置.get("混合液实测RI", "")), key=f"混合RI_{批次编号}")
    混溶 = 中.text_input("实验混溶性", value=str(设置.get("实验混溶性", "")), key=f"混溶_{批次编号}")
    稳定性 = 右.text_input("稳定性状态", value=str(设置.get("稳定性状态", "")), key=f"稳定性_{批次编号}")
    水相分离 = st.text_input("水触发相分离", value=str(设置.get("水触发相分离", "")), key=f"水相分离_{批次编号}")
    if st.button("保存配方层数据", key=f"保存配方_{批次编号}"):
        保存配方设置(管理器, 批次编号, 设置 | {"混合液实测RI": 混合RI, "实验混溶性": 混溶, "稳定性状态": 稳定性, "水触发相分离": 水相分离})
        st.success("已保存配方层观察数据。")

    _物性录入(管理器, 批次编号, 成分证据, 读取配方设置(管理器, 批次编号), 元数据)

    if st.button("运行颅骨透明化用途评估", type="primary", key=f"评估_{批次编号}"):
        try:
            结果 = 运行用途评估(管理器, 批次编号, 清单, {键: 元数据.get(键) for 键 in ("用途标识", "用途名称", "用途配置版本", "目标折射率", "温度_C", "HSP参照体系")})
        except (ValueError, TypeError) as 错误:
            st.error(f"用途评估未完成，请检查配置：{错误}")
            return
        st.success("用途评估完成；缺失字段会显示为待补，不会生成虚构预测。")
        st.dataframe(结果["配方摘要"], use_container_width=True, hide_index=True)
        st.subheader("配方物性与证据状态")
        物性显示 = 结果["配方物性"].copy()
        物性显示["警告"] = 物性显示["警告"].map(lambda x: "；".join(x))
        st.dataframe(物性显示.drop(columns=["依赖", "条件", "模型参数"], errors="ignore"), use_container_width=True, hide_index=True)
        st.caption("模型预测和实测分别标记。自由扩散不代表组织递送效果；缺失毒理与滞留证据保持未知。")
        st.dataframe(结果["用途约束"], use_container_width=True, hide_index=True)
        if not 结果["组分HSP结果"].empty:
            st.caption("多化合物组分两两 HSP 距离：用于识别配方内部的相容性风险，不替代实验混溶性。")
            st.dataframe(结果["组分HSP结果"], use_container_width=True, hide_index=True)
        st.dataframe(结果["配方特征"], use_container_width=True, hide_index=True)
