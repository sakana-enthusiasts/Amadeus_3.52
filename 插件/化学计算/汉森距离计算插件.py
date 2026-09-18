"""基于论文 dD/dP/dH 参数独立计算补充数据3候选的 Hansen 距离。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口
from 插件.化学计算.HSP计算核心 import HSP计算核心


class 汉森距离计算插件(基础插件接口):
    插件标识 = "汉森距离计算"
    输入标识 = "补充数据3_结构映射结果"
    输出标识 = "补充数据3_汉森距离结果"
    参数来源 = "SeeThrough Supplementary Data 3"
    公式 = "Ra = sqrt(4*(dD1-dD2)^2 + (dP1-dP2)^2 + (dH1-dH2)^2)"

    @staticmethod
    def 计算距离(候选参数: pd.Series, 参照参数: pd.Series) -> float:
        return HSP计算核心.计算距离(候选参数, 参照参数)

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        全部试剂 = 数据管理器.读取中间结果(self.输入标识)
        参照 = {名称: 全部试剂.loc[全部试剂["候选编号"].eq(名称)].iloc[0] for 名称 in ("BA", "VA")}
        水相候选 = 全部试剂.loc[全部试剂["试剂角色"].eq("水相候选")]
        结果记录: list[dict[str, Any]] = []
        for _, 候选 in 水相候选.iterrows():
            for 参照编号, 参照试剂 in 参照.items():
                结果记录.append(
                    {
                        "候选编号": 候选["候选编号"],
                        "候选名称": 候选["论文_化学名称"],
                        "参照试剂编号": 参照编号,
                        "参照试剂名称": 参照试剂["论文_化学名称"],
                        "候选_dD": 候选["论文_dD"], "候选_dP": 候选["论文_dP"], "候选_dH": 候选["论文_dH"],
                        "参照_dD": 参照试剂["论文_dD"], "参照_dP": 参照试剂["论文_dP"], "参照_dH": 参照试剂["论文_dH"],
                        "汉森距离_Ra": round(self.计算距离(候选, 参照试剂), 6),
                        "计算公式": self.公式,
                        "数据来源": self.参数来源,
                    }
                )
        结果 = pd.DataFrame(结果记录)
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果
