from math import pi

from .接口 import 扩散模型接口
from ..配方物性接口 import 有限数, 输入不可用


class StokesEinstein模型(扩散模型接口):
    方法 = "stokes_einstein"
    依赖指标 = ("混合黏度",)
    适用范围 = "给定水动力半径探针在连续介质中的自由扩散近似；不等于颅骨组织扩散"

    def 预测(self, 配方, 上游):
        黏度 = 上游.get("混合黏度")
        if 黏度 is None or 黏度.状态 not in {"已预测", "已实测"}:
            raise 输入不可用("上游混合黏度不可用")
        if 黏度.单位 != "mPa·s":
            raise 输入不可用("上游黏度单位必须为 mPa·s")
        eta = 有限数(黏度.值, "混合黏度", 严格正=True) * 1e-3
        半径 = 有限数(配方.条件.get("探针水动力半径_nm"), "探针水动力半径_nm", 严格正=True) * 1e-9
        D = 1.380649e-23 * 配方.温度K() / (6 * pi * eta * 半径)
        return self.结果(D, 警告=("仅代表指定探针；未计组织孔隙、结合、washout 或局部滞留",) + tuple(黏度.警告),
                         依赖={"混合黏度": 黏度.转字典()})
