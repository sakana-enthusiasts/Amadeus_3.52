from math import exp

from .接口 import 黏度模型接口
from .理想对数混合 import 对数基项
from ..配方物性接口 import 有限数, 输入不可用


class GrunbergNissan模型(黏度模型接口):
    方法 = "grunberg_nissan"
    自动优先级 = 10
    适用范围 = "摩尔分数；每个组分对的 Gij 必须对应当前体系与温度；多元使用两两项近似"

    def 预测(self, 配方, 上游):
        成分, 基项 = 对数基项(配方)
        参数 = 配方.参数.get(self.方法, {})
        系数 = 参数.get("Gij", {})
        if len(成分) > 1:
            温度 = 有限数(参数.get("温度_C"), "Gij 温度_C")
            if abs(温度 - (配方.温度K() - 273.15)) > 1e-6:
                raise 输入不可用("Gij 温度与配方温度不一致")
        键 = [str(行.get("成分键", "")) for 行, _ in 成分]
        if any(not k for k in 键) or len(set(键)) != len(键):
            raise 输入不可用("Gij 需要唯一非空成分键")
        for i, (_, xi) in enumerate(成分):
            for j in range(i + 1, len(成分)):
                a, b = sorted((键[i], 键[j]))
                g = 有限数(系数.get(a, {}).get(b), f"Gij[{a}][{b}]")
                基项 += xi * 成分[j][1] * g
        return self.结果(exp(基项), 警告=("Gij 由用户提供，需核实其校准来源与适用组成范围",))
