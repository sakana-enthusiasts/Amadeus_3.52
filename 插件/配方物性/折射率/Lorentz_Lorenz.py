from math import sqrt

from .接口 import 折射率模型接口
from ..配方物性接口 import 有限数


class LorentzLorenz模型(折射率模型接口):
    方法 = "lorentz_lorenz"
    适用范围 = "均一液体、体积可加近似；纯组分 RI 须对应相同温度和波长"

    def 预测(self, 配方, 上游):
        配方.温度K()
        混合 = 0.0
        for 行, phi in 配方.分数("体积分数"):
            n = 有限数(行.get("纯物质RI"), "纯物质RI", 最小=1)
            混合 += phi * (1 - 3 / (n * n + 2))
        return self.结果(sqrt((1 + 2 * 混合) / (1 - 混合)), 警告=("忽略混合体积变化；未验证输入 RI 的温度和波长一致性",))
