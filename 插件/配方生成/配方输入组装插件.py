"""显式用量 → 质量、摩尔及纯组分等效体积分数；不猜测缺失溶剂。"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from math import isclose

from 插件.插件接口 import 基础插件接口
from 插件.配方物性.配方物性接口 import 有限数, 输入不可用


分数单位 = {"质量分数": ("g", 100), "摩尔分数": ("mol", 1), "体积分数": ("mL", 100)}


class 配方输入组装插件(基础插件接口):
    插件标识 = "配方输入组装"
    版本 = "1.0"

    def 执行(self, 数据上下文):
        定义 = deepcopy(数据上下文["配方定义"])
        库 = {str(x["物质编号"]): deepcopy(x) for x in 数据上下文["物质库"]}
        if len(库) != len(数据上下文["物质库"]):
            raise ValueError("物质库编号重复")
        组分 = 定义.get("组分", [])
        if not 组分:
            raise ValueError("需要完整配方组分及用量")
        标识们 = [str(x["物质编号"]) for x in 组分]
        if len(set(标识们)) != len(标识们) or set(标识们) - set(库):
            raise ValueError("配方组分编号重复或不在物质库中")
        if not any(x.get("角色") == "主溶剂" for x in 组分):
            if not (len(组分) == 1 and 定义.get("纯组分验证") is True):
                raise ValueError("不能将单个候选直接作为配方：必须显式加入主溶剂")
        if any(x.get("角色") not in {"主溶剂", "共溶剂", "候选成分"} for x in 组分):
            raise ValueError("组分角色必须为主溶剂、共溶剂或候选成分")
        单位们 = {x["单位"] for x in 组分}
        if 单位们 & set(分数单位):
            if len(单位们) != 1:
                raise ValueError("分数输入必须使用同一种基准；不可与绝对用量混用")
            单位 = next(iter(单位们))
            分数们 = [有限数(x["用量"], 单位, 严格正=True) for x in 组分]
            if not isclose(sum(分数们), 1, abs_tol=1e-6, rel_tol=0):
                raise ValueError("分数之和必须为1；请明确填写剩余溶剂")
            基准单位, 倍率 = 分数单位[单位]
            for x, f in zip(组分, 分数们):
                x["用量"], x["单位"] = f * 倍率, 基准单位
        elif not 单位们.issubset({"g", "mg", "mL", "uL", "mol", "mmol"}):
            raise ValueError("不支持裸%、w/v%、饱和或未定义单位；请给出实际用量")
        条件 = deepcopy(数据上下文.get("物性条件") or {})
        温度 = 有限数(条件.get("温度_C"), "配方温度_C")
        if 温度 <= -273.15:
            raise ValueError("温度必须高于绝对零度")
        波长 = 条件.get("波长_nm")
        警告, 缺失, 输出 = [], [], []
        if sum(x.get("角色") == "主溶剂" for x in 组分) > 1:
            raise ValueError("只能指定一个主溶剂；其余请标为共溶剂")
        CAS们 = [库[i].get("CAS") for i in 标识们 if 库[i].get("CAS")]
        if len(CAS们) != len(set(CAS们)):
            raise ValueError("同一CAS不能以多个别名重复投料")
        for 组 in 组分:
            编号 = str(组["物质编号"])
            物质 = 库[编号]
            if 物质.get("数据说明"):
                警告.append(f"{编号}：{物质['数据说明']}")
            行 = {**物质, "成分键": 编号, "候选编号": 编号, "配方角色": 组["角色"]}
            # 库中的分数、浓度及实验标签永远不能覆盖本次组装结果。
            for 字段 in ("质量分数", "摩尔分数", "体积分数", "摩尔浓度_mol_L", "浓度值", "浓度单位"):
                行.pop(字段, None)
            mw = 有限数(物质.get("分子量_g_mol"), f"{编号}分子量", 严格正=True)
            rho = None
            try:
                rho = 有限数(物质.get("密度_g_mL"), f"{编号}密度", 严格正=True)
                密度温度 = 有限数(物质.get("密度温度_C"), f"{编号}密度温度")
                if abs(密度温度 - 温度) > 1e-6:
                    raise 输入不可用(f"{编号}密度温度与配方不符，未自动外推")
            except 输入不可用 as e:
                缺失.append(str(e))
                rho = None
            数 = 有限数(组["用量"], f"{编号}用量", 严格正=True)
            单位 = 组["单位"]
            if 单位 in {"g", "mg"}:
                质量 = 数 * (1e-3 if 单位 == "mg" else 1)
            elif 单位 in {"mol", "mmol"}:
                质量 = 数 * (1e-3 if 单位 == "mmol" else 1) * mw
            else:
                if rho is None:
                    raise ValueError(f"{编号}按体积投料，需要对应温度的密度才能换算质量和摩尔数")
                质量 = 数 * (1e-3 if 单位 == "uL" else 1) * rho
            行.update({"质量_g": 质量, "物质的量_mol": 质量 / mw,
                       "纯组分等效体积_mL": 质量 / rho if rho is not None else None})
            for 字段, 温度字段, 需波长 in (("纯物质RI", "RI温度_C", True), ("纯物质黏度_mPa_s", "黏度温度_C", False)):
                try:
                    有限数(行.get(字段), f"{编号}{字段}", 严格正=True)
                    if 物质.get("相态") != "液体":
                        raise 输入不可用(f"{编号}为非液体；固体eRI/黏度不能替代纯液体物性")
                    if abs(有限数(物质.get(温度字段), f"{编号}{温度字段}") - 温度) > 1e-6:
                        raise 输入不可用(f"{编号}{字段}温度不匹配")
                    if 需波长 and (波长 is None or abs(有限数(物质.get("RI波长_nm"), "RI波长") - 有限数(波长, "配方波长")) > 1):
                        raise 输入不可用(f"{编号}RI波长缺失或不匹配")
                except 输入不可用 as e:
                    行[字段] = None
                    缺失.append(str(e))
            if 物质.get("相态") != "液体":
                警告.append(f"{编号}等效固体体积不是溶解后的偏摩尔体积，体积分数只作记账近似")
            输出.append(行)
        总质量 = sum(x["质量_g"] for x in 输出)
        总摩尔 = sum(x["物质的量_mol"] for x in 输出)
        总等效体积 = sum(x["纯组分等效体积_mL"] for x in 输出) if all(x["纯组分等效体积_mL"] is not None for x in 输出) else None
        最终体积 = 定义.get("最终体积_mL")
        if 最终体积 is not None:
            最终体积 = 有限数(最终体积, "最终体积_mL", 严格正=True)
            if not 定义.get("最终体积来源"):
                raise ValueError("最终体积需要数据来源")
            体积依据 = "用户提供最终体积：" + 定义["最终体积来源"]
        elif 定义.get("体积策略") == "纯组分体积可加" and 总等效体积 is not None:
            最终体积, 体积依据 = 总等效体积, "纯组分体积可加估算"
            警告.append("最终体积由纯组分体积相加估算，未考虑收缩/膨胀；浓度及渗透压继承此误差")
        else:
            最终体积, 体积依据 = None, "缺少最终体积"
            缺失.append("最终体积或显式体积可加假设")
        参照溶剂 = 定义.get("渗透参照溶剂")
        if 参照溶剂 is not None and 参照溶剂 not in 标识们:
            raise ValueError("渗透参照溶剂不在配方中")
        for 行 in 输出:
            行.update({"质量分数": 行["质量_g"] / 总质量, "摩尔分数": 行["物质的量_mol"] / 总摩尔,
                       "体积分数": 行["纯组分等效体积_mL"] / 总等效体积 if 总等效体积 else None,
                       "摩尔浓度_mol_L": 行["物质的量_mol"] / (最终体积 * 1e-3) if 最终体积 else None,
                       "浓度值": 行["质量_g"] / 总质量 * 100, "浓度单位": "w/w%",
                       "渗透角色": ("溶剂" if 行["成分键"] == 参照溶剂 else "溶质") if 参照溶剂 else ""})
        if not 参照溶剂:
            缺失.append("渗透参照溶剂")
        水 = [x["成分键"] for x in 输出 if x.get("CAS") == "7732-18-5"]
        if len(水) == 1:
            条件["水成分键"] = 水[0]
        if 定义.get("扩散探针"):
            探针 = 定义["扩散探针"]
            条件["探针水动力半径_nm"] = 有限数(探针.get("半径_nm"), "探针水动力半径", 严格正=True)
            if not 探针.get("名称") or not 探针.get("来源"):
                raise ValueError("扩散探针需要名称和半径来源，不能默认为候选分子")
            条件["探针名称"], 条件["探针来源"] = 探针["名称"], 探针["来源"]
        稳定信息 = {"组成": sorted((x["成分键"], round(x["质量分数"], 12)) for x in 输出), "定义": 定义, "条件": 条件}
        编号 = "form_" + sha256(json.dumps(稳定信息, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
        return {"配方编号": 编号, "配方名称": 定义.get("配方名称", 编号), "成分": 输出, "物性条件": 条件,
                "配方定义": 定义, "组装版本": self.版本, "组装状态": "已组装" if 总等效体积 and 最终体积 else "部分组装",
                "质量总和_g": 总质量, "摩尔总和_mol": 总摩尔, "最终体积_mL": 最终体积,
                "体积依据": 体积依据, "组装警告": list(dict.fromkeys(警告)), "组装缺失": list(dict.fromkeys(缺失))}
