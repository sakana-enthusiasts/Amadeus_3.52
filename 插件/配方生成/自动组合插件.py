"""只从独立候选池生成配方。主体由相态和本次比例决定，无指定化学名称。"""

from itertools import combinations
from math import comb
from 插件.插件接口 import 基础插件接口


def 整数分割(总数, 长度):
    if 长度 == 1:
        yield (总数,)
    else:
        for 首项 in range(1, 总数-长度+2):
            for 剩余 in 整数分割(总数-首项, 长度-1):
                yield (首项, *剩余)


def 组装定义(组成, 库, 配置):
    液体 = [i for i in 组成 if 库[i].get("相态") == "液体"]
    if not 液体:
        return None
    主 = sorted(液体, key=lambda i: (-组成[i], i))[0]
    组分 = [{"物质编号": i, "用量": f, "单位": "质量分数",
             "角色": "主溶剂" if i == 主 else "共溶剂" if i in 液体 else "候选成分"} for i, f in sorted(组成.items())]
    名称 = " + ".join(f"{库[x['物质编号']].get('化学名称', x['物质编号'])} {x['用量']:.1%}" for x in 组分)
    return {"配方名称": 名称 + " (w/w)", "组分": 组分, "体积策略": "纯组分体积可加",
            "渗透参照溶剂": 主, "扩散探针": 配置.get("扩散探针"),
            "生成来源": "独立候选池；按质量占比自动选择液体主体；渗透压相对于该主体"}


class 自动组合插件(基础插件接口):
    插件标识 = "自动配方组合"

    def 执行(self, 数据上下文):
        配置, 物质们 = 数据上下文["生成配置"], 数据上下文["物质库"]
        库 = {x["物质编号"]: x for x in 物质们}
        if len(库) != len(物质们) or len(库) > 100:
            raise ValueError("物质编号重复或筛后池超过100种；请先收紧分子约束")
        CAS们 = [x.get("CAS") for x in 物质们 if x.get("CAS")]
        if len(CAS们) != len(set(CAS们)):
            raise ValueError("候选池含重复CAS别名")
        for x in 物质们:
            if x.get("来源类型") not in {"独立公开物性", "用户独立输入"} or not x.get("数据来源"):
                raise ValueError(f"{x['物质编号']}不是有来源的独立候选，不能导入验证/论文专用记录")
        步长 = 配置.get("粗搜步长百分比", 20)
        最小, 最大 = 配置.get("最小组分数", 1), 配置.get("最大组分数", 3)
        上限 = 配置.get("最大配方数", 2000)
        if isinstance(步长, bool) or 步长 not in {5, 10, 20, 25, 50}:
            raise ValueError("粗搜步长须为5、10、20、25或50质量百分点")
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (最小, 最大, 上限)) or not 1 <= 最小 <= 最大 <= 6 or not 1 <= 上限 <= 5000:
            raise ValueError("组分数范围须在1–6，枚举上限须在1–5000")
        格数 = 100 // 步长
        组合们, 预计 = [], 0
        for k in range(最小, min(最大, len(库), 格数)+1):
            for c in combinations(sorted(库), k):
                if not any(库[i].get("相态") == "液体" for i in c):
                    continue
                预计 += comb(格数-1, len(c)-1)
                if 预计 > 上限:
                    raise ValueError(f"完整粗搜超过预算{上限}；请收紧分子约束或增大步长，不按池顺序截断")
                组合们.append(c)
        return [组装定义(dict(zip(c, (n/格数 for n in 分配))), 库, 配置)
                for c in 组合们 for 分配 in 整数分割(格数, len(c))]
