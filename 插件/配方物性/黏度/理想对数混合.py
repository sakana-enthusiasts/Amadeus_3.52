from math import exp, log

from .接口 import 黏度模型接口
from ..配方物性接口 import 有限数


def 对数基项(配方):
    配方.温度K()
    成分 = 配方.分数("摩尔分数")
    return 成分, sum(x * log(有限数(行.get("纯物质黏度_mPa_s"), "纯物质黏度_mPa_s", 严格正=True)) for 行, x in 成分)


class 理想对数混合模型(黏度模型接口):
    方法 = "ideal_log"
    适用范围 = "理想对数混合；摩尔分数；输入黏度须对应配方温度"

    def 预测(self, 配方, 上游):
        _, 基项 = 对数基项(配方)
        return self.结果(exp(基项), 警告=("低可信：未计入组分相互作用；温度一致性须由输入来源确认",))
