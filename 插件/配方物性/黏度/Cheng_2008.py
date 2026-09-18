"""Cheng (2008), DOI 10.1021/ie071349z；仅甘油–水，不推广到其他组分。"""

from dataclasses import replace
from math import exp

from .接口 import 黏度模型接口
from ..配方物性接口 import 输入不可用


def 纯水黏度(T):
    return 1.790 * exp((-1230 - T) * T / (36100 + 360 * T))


def 纯甘油黏度(T):
    return 12100 * exp((-1233 + T) * T / (9900 + 70 * T))


class Cheng甘油水模型(黏度模型接口):
    方法 = "cheng_glycerol_water_2008"
    自动优先级 = 5  # 有同条件Gij时优先使用已校准模型，其次才是甘油水经验式。
    适用范围 = "仅水/甘油、质量分数0–1、0–100°C；文献经验关系，非通用混合规则"

    def 预测(self, 配方, 上游):
        T = 配方.温度K() - 273.15
        if not 0 <= T <= 100:
            raise 输入不可用("Cheng模型仅支持0–100°C")
        成分 = 配方.分数("质量分数")
        if any(x.get("CAS") not in {"56-81-5", "7732-18-5"} for x, _ in 成分):
            raise 输入不可用("Cheng模型仅适用于甘油–水")
        w = sum(f for x, f in 成分 if x.get("CAS") == "56-81-5")
        a = 0.705 - 0.0017 * T
        b = (4.9 + 0.036 * T) * a**2.5
        alpha = 1 - w + a * b * w * (1 - w) / (a * w + b * (1 - w))
        值 = 纯水黏度(T)**alpha * 纯甘油黏度(T)**(1 - alpha)
        return replace(self.结果(值), 数据来源="Cheng 2008, https://doi.org/10.1021/ie071349z",
                       警告=("文献经验相关式；本项目未量化当前配方的预测区间",))
