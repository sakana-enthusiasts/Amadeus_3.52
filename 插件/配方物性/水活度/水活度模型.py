from .接口 import 水活度模型接口
from ..配方物性接口 import 有限数, 输入不可用


def 水摩尔分数(配方):
    配方.温度K()
    水键 = str(配方.条件.get("水成分键", ""))
    if not 水键 or sum(str(行.get("成分键", "")) == 水键 for 行 in 配方.成分) != 1:
        raise 输入不可用("需要唯一的水成分键，不能从化学名称猜测水")
    return sum(x for 行, x in 配方.分数("摩尔分数") if str(行.get("成分键", "")) == 水键)


class 理想水活度模型(水活度模型接口):
    方法 = "ideal_water_activity"
    适用范围 = "理想液体混合物；aw = xw；不适用于强非理想或电解质体系"

    def 预测(self, 配方, 上游):
        return self.结果(水摩尔分数(配方), 警告=("低可信：水活度理想近似；不直接推断组织脱水比例",))


class 活度系数水活度模型(水活度模型接口):
    方法 = "water_activity_coefficient"
    自动优先级 = 10
    适用范围 = "aw = gamma_w * xw；需当前配方和温度的水活度系数"

    def 预测(self, 配方, 上游):
        gamma = 有限数(配方.参数.get(self.方法, {}).get("水活度系数"), "水活度系数", 严格正=True)
        aw = gamma * 水摩尔分数(配方)
        if aw > 1:
            raise 输入不可用("水活度超出本模型支持的 0 到 1 范围")
        return self.结果(aw, 警告=("需核实活度系数的配方与温度适用性",))
