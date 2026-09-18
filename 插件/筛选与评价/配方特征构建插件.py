"""将用途层已经验证的数据整理为算法接口输入，不负责训练或预测。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 配方特征构建插件(基础插件接口):
    插件标识 = "配方特征构建"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        摘要 = 数据上下文.get("配方摘要")
        特征 = 摘要.copy() if isinstance(摘要, pd.DataFrame) else pd.DataFrame([] if 摘要 is None else 摘要)
        if 特征.empty:
            return pd.DataFrame(columns=["预测器输入状态", "优化器输入状态"])
        缺项 = list(数据上下文.get("缺失项") or [])
        特征["预测器输入状态"] = "可作为接口输入，仍需已训练模型" if not 缺项 else "待补：" + "、".join(缺项)
        实验数 = int(数据上下文.get("有效实验终点数", 0) or 0)
        特征["优化器输入状态"] = "可记录实验终点后进入接口" if 实验数 else "待补实验终点"
        return 特征
