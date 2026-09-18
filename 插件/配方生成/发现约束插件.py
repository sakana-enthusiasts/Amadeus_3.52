"""用户约束与证据分开：未知不等于通过，GHS不折算成配方毒性。"""

from 插件.插件接口 import 基础插件接口
from 插件.配方物性.配方物性接口 import 有限数, 输入不可用
from .比例优化插件 import 组成签名


def 检查范围(值, 范围):
    if not isinstance(范围, dict) or not 范围 or set(范围) - {"最小", "最大"}:
        raise ValueError("数值约束必须包含最小/最大")
    下限 = 有限数(范围["最小"], "约束下限") if "最小" in 范围 else None
    上限 = 有限数(范围["最大"], "约束上限") if "最大" in 范围 else None
    if 下限 is not None and 上限 is not None and 下限 > 上限:
        raise ValueError("约束下限不能超过上限")
    try:
        数 = 有限数(值, "约束值")
    except 输入不可用:
        return "未知"
    return "不满足" if (下限 is not None and 数 < 下限) or (上限 is not None and 数 > 上限) else "满足"


def 评价规格指标(项, 对象):
    """现有约束路径的正式规格适配；保留原始值与合格值的区别。"""
    c, b = 项.criterion, 项.binding
    if b.source == "配方物性":
        r = 对象.get("配方物性", {}).get(b.field, {})
        值, 单位, 来源 = r.get("值"), r.get("单位"), r.get("数据来源")
        类型 = {"已预测": "predicted", "已实测": "measured"}.get(r.get("状态"))
        原因 = "；".join(r.get("警告", [])) if 值 is None else ""
        条件 = r.get("条件", {})
    else:
        值, 单位 = 对象.get(b.field), b.unit
        来源 = (对象.get("数据来源") if b.scope == "molecule" else
                [x.get("数据来源") for x in 对象.get("成分", [])])
        类型 = "unspecified" if b.scope == "molecule" else "derived"
        原因, 条件 = "", 对象.get("物性条件", {})
    合格 = None
    try:
        合格 = 有限数(值, 项.metric_id)
    except 输入不可用:
        原因 = 原因 or "缺少有限数值"
    if not 来源 or (isinstance(来源, list) and not all(来源)):
        合格, 原因 = None, "缺少明确数据来源"
    if 单位 != b.unit:
        合格, 原因 = None, "原始单位与标准单位不兼容"
    if b.source == "配方物性" and 类型 is None:
        合格, 原因 = None, "结果状态不是合格实测或预测"
    if c.evidence_requirement != "any" and (类型 not in {"measured", "predicted"} or
            (c.evidence_requirement == "measured_only" and 类型 != "measured")):
        合格, 原因 = None, "证据类型不满足 evidence_requirement"
    判断 = None
    if c.role == "hard_constraint":
        if c.equals is not None:
            判断 = "未知" if not isinstance(值, bool) else "满足" if 值 == c.equals else "不满足"
        else:
            范围 = ({"最小": c.lower} if c.lower is not None else {}) | ({"最大": c.upper} if c.upper is not None else {})
            判断 = 检查范围(合格, 范围)
    return {"metric_id": 项.metric_id, "role": c.role, "scope": b.scope,
            "值": 值, "合格值": 合格, "原始单位": 单位, "标准单位": b.unit,
            "状态": "unknown" if 合格 is None else "available", "缺失原因": 原因 or None,
            "数据来源": 来源, "证据类型": 类型, "条件": 条件,
            "missing_policy": c.missing_policy, "evidence_requirement": c.evidence_requirement,
            "hard_constraint判断": 判断,
            "objective transformation": c.to_dict() if c.role == "objective" else None}


class 候选分子筛选插件(基础插件接口):
    插件标识 = "独立候选分子筛选"

    def 执行(self, 数据上下文):
        约束 = 数据上下文.get("约束", {})
        保留, 排除 = [], []
        计划 = 数据上下文.get("执行计划")
        for 原 in 数据上下文["物质库"]:
            行, 理由 = dict(原), []
            if 行.get("来源类型") not in {"独立公开物性", "用户独立输入"} or not 行.get("数据来源"):
                理由.append("来源未标明独立；Benchmark不能作为发现池")
            if 行.get("CAS") in 约束.get("排除CAS", []):
                理由.append("用户排除CAS")
            for 必填 in ("物质编号", "化学名称"):
                if not 行.get(必填):
                    理由.append(f"缺{必填}")
            try:
                有限数(行.get("分子量_g_mol"), "分子量", 严格正=True)
            except 输入不可用:
                理由.append("缺可用于组装的分子量")
            for 字段, 范围 in 约束.get("分子约束", {}).items():
                状态 = 检查范围(行.get(字段), 范围)
                if 状态 != "满足":
                    理由.append(f"分子约束{字段}：{状态}")
            if 约束.get("要求可购") and 行.get("可购性") != "可购":
                理由.append("可购性不满足或未知")
            规格评价 = [评价规格指标(x, 行) for x in 计划.criteria if x.binding.scope == "molecule"] if 计划 else []
            for r in 规格评价:
                if r["role"] == "hard_constraint" and (r["hard_constraint判断"] == "不满足" or
                        (r["状态"] == "unknown" and r["missing_policy"] == "exclude")):
                    理由.append(f"Target Profile {r['metric_id']}：{r['hard_constraint判断']}")
            if 计划:
                行["目标规格评价"] = 规格评价
            if 理由:
                排除.append({"物质编号": 行.get("物质编号"), "化学名称": 行.get("化学名称"), "原因": "；".join(理由),
                             **({"目标规格评价": 规格评价} if 计划 else {})})
            else:
                # 论文派生分数与标签不传给生成、预测或优化。
                保留.append({k: v for k, v in 行.items() if not k.startswith("论文") and k not in {"eRI", "论文排名", "参考得分"}})
        return {"物质库": 保留, "排除分子": 排除}


class 配方约束评价插件(基础插件接口):
    插件标识 = "发现配方约束评价"

    def 执行(self, 数据上下文):
        配方, 约束 = 数据上下文["配方"], 数据上下文.get("约束", {})
        检查, 物性 = [], 配方["配方物性"]
        策略 = 约束.get("缺失策略", "保留待补")
        if 策略 not in {"保留待补", "排除"}:
            raise ValueError("约束缺失策略应为保留待补或排除")
        for 指标, 范围 in 约束.get("物性约束", {}).items():
            if 指标 not in 物性:
                raise ValueError(f"未知约束指标：{指标}")
            检查.append({"指标": 指标, "值": 物性[指标]["值"], "单位": 物性[指标]["单位"],
                         "状态": 检查范围(物性[指标]["值"], 范围), "依据": "模型试算，尚未实验验证"})
        成分 = 配方["成分"]
        成本 = None
        try:
            成本 = sum(x["质量分数"] * 有限数(x.get("价格_元_kg"), "价格", 最小=0) for x in 成分)
        except 输入不可用:
            pass
        if "成本上限_元_kg" in 约束:
            检查.append({"指标": "成本", "值": 成本, "单位": "元/kg", "状态": 检查范围(成本, {"最大": 约束["成本上限_元_kg"]}), "依据": "输入价格按质量加权，不含制备成本"})
        # 实测配方证据必须完全对应组分/比例，不从纯物质或二元数据外推到三元。
        签名 = 组成签名(配方["配方定义"])
        证据 = [e for e in 数据上下文.get("配方证据", []) if
                tuple(sorted((i, round(float(f), 10)) for i, f in e.get("质量分数组成", []))) == 签名 and e.get("数据来源")]
        毒理条件 = 约束.get("毒理条件", {})
        毒理 = [e for e in 证据 if e.get("指标") == "局部细胞存活率" and e.get("单位") == "%" and 毒理条件
                and all(e.get("条件", {}).get(k) == v for k, v in 毒理条件.items())
                and all(毒理条件.get(k) is not None for k in ("物种", "组织", "给药途径", "剂量", "剂量单位", "暴露时长_h"))]
        值 = None
        if len(毒理) == 1:
            try:
                值 = 有限数(毒理[0].get("值"), "局部细胞存活率", 最小=0)
                if 值 > 100:
                    值 = None
            except 输入不可用:
                pass
        毒理状态 = 检查范围(值, {"最小": 约束["细胞存活率下限_pct"]}) if "细胞存活率下限_pct" in 约束 else "未知"
        检查.append({"指标": "局部细胞存活率", "值": 值, "单位": "%", "状态": 毒理状态,
                     "依据": "同配方同暴露条件证据" if len(毒理) == 1 and 值 is not None else "缺少唯一且条件匹配的配方证据；GHS不是配方毒性"})
        相证据 = [e for e in 证据 if e.get("指标") == "相稳定性" and e.get("条件", {}).get("温度_C") == 配方["物性条件"]["温度_C"]]
        相状态 = ("满足" if 相证据[0].get("值") == "单相稳定" else "不满足") if len(相证据) == 1 and 相证据[0].get("值") in {"单相稳定", "沉淀", "分层"} else "未知"
        检查.append({"指标": "溶解/相稳定性", "状态": 相状态, "依据": "当前组成及温度的实验记录；不将纯溶剂溶解度视为多元混溶性"})
        违反 = any(x["状态"] == "不满足" for x in 检查)
        未知 = any(x["状态"] == "未知" for x in 检查)
        计划 = 数据上下文.get("执行计划")
        规格评价 = []
        if 计划:
            对象 = 配方 | {"成本_元_kg": 成本}
            规格评价 = [评价规格指标(x, 对象) for x in 计划.criteria if x.binding.scope == "formulation"]
            规格评价 += [r | {"物质编号": x["成分键"]} for x in 成分 for r in x.get("目标规格评价", [])]
            规格评价 += [{"metric_id": metric_id, "role": "disabled", "值": None,
                          "合格值": None, "原始单位": None, "状态": "disabled",
                          "缺失原因": None, "hard_constraint判断": None,
                          "objective transformation": None} for metric_id in 计划.disabled]
        硬检查 = [r for r in 规格评价 if r["role"] == "hard_constraint"]
        规格违反 = any(r["hard_constraint判断"] == "不满足" or
                    (r["状态"] == "unknown" and r["missing_policy"] == "exclude") for r in 硬检查)
        规格未知 = any(r["状态"] == "unknown" for r in 硬检查)
        目标缺失排除 = any(r["role"] == "objective" and r["合格值"] is None and
                           r["missing_policy"] == "exclude" for r in 规格评价)
        for r in 硬检查:
            检查.append({"指标": r["metric_id"], "值": r["值"], "单位": r["原始单位"],
                         "状态": r["hard_constraint判断"], "来源": "Target Profile"})
        if 计划:
            for r in 检查:
                r.setdefault("来源", "legacy")
        return {"约束检查": 检查, "约束状态": "不满足" if 违反 else "待补证据" if 未知 else "满足已配置约束",
                "可参与排序": not 违反 and (策略 == "保留待补" or not 未知) and not 规格违反 and not 目标缺失排除,
                **({"目标规格评价": 规格评价, "约束状态": "不满足" if 违反 or 规格违反 else
                    "待补证据" if 未知 or 规格未知 else "满足已配置约束"} if 计划 else {}),
                "成本_元_kg": 成本, "局部细胞存活率_pct": 值}
