"""独立于已确认论文批次的研发入口；界面不包含生成或评分算法。"""

import json
import pandas as pd
import streamlit as st

from 核心系统.配方研发流程 import 运行验证模式, 运行发现模式, 研发默认模型
from 设置.公开物性样例 import 公开物性演示库, 默认发现配置
from 插件.配方物性.配方物性汇总 import 创建默认模型注册表


def _json(值):
    return json.dumps(值, ensure_ascii=False, indent=2, allow_nan=False)


def _表(记录):
    # 嵌套证据在表中转文本，完整结构保存在下载结果中。
    return pd.DataFrame([{k: _json(v) if isinstance(v, (list, dict, tuple)) else v for k, v in x.items()} for x in 记录])


def 候选概览(候选):
    return [{"配方": x["配方名称"], "Pareto层": x.get("非支配层"),
             **{f"{k} [{v['单位']}]": v["值"] for k, v in x["配方物性"].items()},
             "约束状态": x.get("约束状态", "验证对照"), "不确定度": "各项预测区间未量化",
             "为什么入选": x.get("推荐原因", "Benchmark，不参加发现排名"), "缺失数据": "；".join(x["缺失数据"])} for x in 候选]


def _显示配方(配方):
    st.caption(f"{配方['配方名称']}；{配方['体积依据']}")
    st.dataframe(_表(配方["成分"]).reindex(columns=["化学名称", "配方角色", "质量_g", "物质的量_mol",
        "质量分数", "摩尔分数", "体积分数", "摩尔浓度_mol_L", "数据来源"]), hide_index=True, use_container_width=True)
    st.caption("体积分数是投料纯组分的等效体积分数；体积可加估算不代表实测混合体积。")
    st.dataframe(_表(list(配方["配方物性"].values())).drop(columns=["依赖", "模型参数"], errors="ignore"), hide_index=True, use_container_width=True)
    if 配方.get("约束检查"):
        st.dataframe(_表(配方["约束检查"]), hide_index=True, use_container_width=True)
    st.write("待补：" + "；".join(配方["缺失数据"]))


def _模型选择():
    选择 = dict(研发默认模型)
    with st.expander("物性模型（可单独替换）"):
        注册表 = 创建默认模型注册表()
        for 指标, 默认 in 选择.items():
            方法 = list(注册表.方法列表(指标))
            选择[指标] = st.selectbox(指标, 方法, index=方法.index(默认), key="研发模型_"+指标)
        st.caption("auto仅按模型适用范围和输入完整性选择；不会选择或添加任何化合物。")
    return 选择


def 渲染配方研发页面():
    st.header("配方发现与验证")
    st.caption("Benchmark、Candidate pool、Constraints 分开管理。主体和共溶剂由候选池及本次配方决定。")
    模式 = st.radio("研发模式", ["验证模式", "发现模式"], horizontal=True)
    选择 = _模型选择()
    if 模式 == "验证模式":
        st.write("检查甘油–水、BA＋ANP、TDE–水、ECi及OPTIClear协议；分别报告数值、误差和不能计算的原因。")
        st.caption("已知配方用于检查模型及最后对照，不会加入发现池。校准来源复现与独立外部验证分别标记。")
        if st.button("运行文献 Benchmark", type="primary"):
            with st.spinner("组装已知配方并检验物性模型…"):
                try:
                    st.session_state["研发验证结果"] = 运行验证模式(模型选择=选择)
                except (ValueError, TypeError) as e:
                    st.error(str(e))
        r = st.session_state.get("研发验证结果")
        if r:
            st.info(r["门禁范围"])
            st.dataframe(_表(r["检查"]), hide_index=True, use_container_width=True)
            st.dataframe(_表(候选概览([x["预测"] for x in r["体系"]])), hide_index=True, use_container_width=True)
            for x in r["体系"]:
                with st.expander(x["体系"] + "｜" + x["预测"]["配方名称"]):
                    st.write(x["数据说明"])
                    _显示配方(x["预测"])
            st.dataframe(_表(r["待补文献协议"]), hide_index=True, use_container_width=True)
            st.download_button("下载完整验证结果", _json(r), "配方benchmark.json", "application/json")
        return

    st.write("✓ 已知参考体系不参与候选生成　✓ 不作为初始种子　✓ 优化完成后才加载参考体系比较")
    st.subheader("1. Candidate pool：允许搜索什么")
    st.caption("默认候选池为空，没有默认溶剂或默认候选。可输入任意独立来源的液体/固体；已有物性不足的候选会明确列出缺口。")
    上传 = st.file_uploader("导入独立候选库 JSON（记录列表）", type=["json"], key="研发候选上传")
    if 上传 is not None and st.session_state.get("研发上传签名") != 上传.getvalue():
        try:
            新库 = json.loads(上传.getvalue())
            if not isinstance(新库, list) or any(not isinstance(x, dict) for x in 新库):
                raise ValueError("候选库应为记录列表")
            st.session_state["研发候选库"] = 新库
            st.session_state["研发上传签名"] = 上传.getvalue()
            st.session_state["研发编辑版本"] = st.session_state.get("研发编辑版本", 0)+1
        except (ValueError, TypeError) as e:
            st.error(f"导入失败：{e}")
    with st.expander("程序试跑数据（不会自动加载）"):
        st.caption("这是一份独立供应商物性快照，仅供检验程序；不代表推荐的透明化化合物。发现算法不依赖其名称或数量。")
        if st.button("载入公开物性演示库"):
            st.session_state["研发候选库"] = 公开物性演示库()
            st.session_state["研发编辑版本"] = st.session_state.get("研发编辑版本", 0)+1
        st.download_button("下载候选库格式示例", _json(公开物性演示库()), "独立候选库示例.json", "application/json")
    库 = st.session_state.get("研发候选库", [])
    列 = ["物质编号", "化学名称", "CAS", "相态", "分子量_g_mol", "密度_g_mL", "密度温度_C", "纯物质RI",
          "RI温度_C", "RI波长_nm", "纯物质黏度_mPa_s", "黏度温度_C", "范特霍夫因子", "来源类型", "数据来源", "价格_元_kg", "可购性"]
    编辑 = st.data_editor(_表(库).reindex(columns=列), num_rows="dynamic", hide_index=True, use_container_width=True,
                       key=f"研发池编辑_{st.session_state.get('研发编辑版本', 0)}")
    st.caption("来源类型填“独立公开物性”或“用户独立输入”；物性必须注明温度，RI还需波长。论文eRI不是纯液体RI。")
    st.subheader("2. Constraints：按什么条件筛选")
    配置 = 默认发现配置()
    a, b, c = st.columns(3)
    配置["目标折射率"] = a.number_input("目标RI", min_value=1.0, value=1.56, step=.01)
    配置["最小组分数"] = int(b.number_input("最少组分数", min_value=1, max_value=6, value=1))
    配置["最大组分数"] = int(c.number_input("最多组分数", min_value=1, max_value=6, value=3))
    策略 = st.selectbox("缺失毒理/相稳定性证据时", ["保留待补", "排除"],
                         help="保留待补仅用于探索；排除模式可能得到零个候选，绝不把未知当安全。")
    约束 = {"缺失策略": 策略}
    if st.checkbox("只考虑已知可购的化合物"):
        约束["要求可购"] = True
    with st.expander("设置物性、分子、成本与毒理约束"):
        st.caption("空白表示未设置阈值；约束单位与物性模型输出一致。")
        物性表 = st.data_editor(pd.DataFrame([{"指标": k, "最小": None, "最大": None} for k in 研发默认模型]),
                               disabled=["指标"], hide_index=True, key="研发物性约束")
        约束["物性约束"] = {r["指标"]: {k: float(r[k]) for k in ("最小", "最大") if pd.notna(r[k])}
                             for r in 物性表.to_dict("records") if any(pd.notna(r[k]) for k in ("最小", "最大"))}
        高级 = st.text_area("其他约束 JSON（可选）", value="{}", help='例如 {"分子约束":{"分子量_g_mol":{"最大":400}},"成本上限_元_kg":500}；毒理条件格式见文档。')
        证据上传 = st.file_uploader("同配方的相稳定性/毒理证据 JSON（可选）", type=["json"])
    with st.expander("搜索范围与预测条件"):
        配置["粗搜步长百分比"] = st.selectbox("粗搜质量百分点", [5, 10, 20, 25, 50], index=2)
        配置["细化步长百分比"] = st.selectbox("局部细化质量百分点", [1, 2, 5, 10], index=2)
        配置["优化轮数"] = int(st.number_input("比例优化轮数", 0, 5, 2))
        配置["最大配方数"] = int(st.number_input("本次配方计算预算", 10, 5000, 2000))
        配置["返回数量"] = int(st.number_input("返回候选数", 5, 10, 8))
        配置["物性条件"]["温度_C"] = st.number_input("预测温度（°C）", value=20.0)
        配置["物性条件"]["波长_nm"] = st.number_input("RI波长（nm）", min_value=1.0, value=589.3)
        配置["扩散探针"]["半径_nm"] = st.number_input("比较用标准探针半径（nm）", min_value=.01, value=1.0)
        配置["扩散探针"]["名称"] = "用户指定标准探针"
        配置["扩散探针"]["来源"] = "界面明确设置的比较探针；不是候选分子的真实半径"
        st.caption("扩散表示上述同一探针在溶液中的自由扩散。渗透压相对于自动选出的液体主体，不是生理渗透压。")
    if st.button("筛分子 → 搜索组合与比例 → Pareto", type="primary", disabled=编辑.empty):
        try:
            附加 = json.loads(高级)
            if not isinstance(附加, dict):
                raise ValueError("约束需为JSON对象")
            约束.update(附加)
            证据 = json.loads(证据上传.getvalue()) if 证据上传 else []
            快照 = 编辑.astype(object).where(pd.notna(编辑), None).to_dict("records")
            # 保留用户导入的非展示字段，例如logP和溶解度来源；编辑字段覆盖原值。
            原库 = {x.get("物质编号"): x for x in 库}
            快照 = [原库.get(x.get("物质编号"), {}) | x for x in 快照]
            with st.spinner("筛分子、组装真实配方并优化比例…"):
                st.session_state["研发发现结果"] = 运行发现模式(快照, 配置, 约束=约束, 配方证据=证据, 模型选择=选择)
        except (ValueError, TypeError, KeyError) as e:
            st.error(f"本次未完成：{e}")
    r = st.session_state.get("研发发现结果")
    if r:
        st.subheader("3. 本次结果")
        st.info(f"{r['状态']}；计算 {r['生成数量']} 个配方，返回 {len(r['候选'])} 个。")
        st.caption("以下保留上次执行时的输入和条件；修改界面后需重新运行。未知毒理不代表低毒。")
        st.dataframe(_表(候选概览(r["候选"])), hide_index=True, use_container_width=True)
        for i, x in enumerate(r["候选"], 1):
            with st.expander(f"{i}. {x['配方名称']}"):
                st.write(x["推荐原因"])
                _显示配方(x)
        with st.expander("完整Pareto前沿、筛除原因及比例优化记录"):
            st.dataframe(_表(候选概览(r.get("Pareto前沿", []))), hide_index=True)
            st.dataframe(_表(r.get("排除分子", []) + r.get("组装失败", []) + [{k: v for k, v in x.items() if k != "配方"} for x in r.get("排除", [])]), hide_index=True)
            st.dataframe(_表(r.get("优化记录", [])), hide_index=True)
        with st.expander("最后对照：新配方与已知体系（不参与排名）"):
            st.dataframe(_表(r.get("最后文献对照", [])), hide_index=True, use_container_width=True)
            st.dataframe(_表(r.get("待补文献协议", [])), hide_index=True)
            st.caption("只比较可比的物性及条件；缺少同条件毒理、递送数据时，不能宣称新配方优于已知方案。")
        st.download_button("下载完整候选、预测和缺失证据", _json(r), "配方发现结果.json", "application/json")
