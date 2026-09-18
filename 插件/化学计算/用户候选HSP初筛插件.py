"""在用户候选初筛阶段，按 SeeThrough 公开参照计算 HSP 距离。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from 插件.化学计算.HSP计算核心 import HSP计算核心
from 插件.插件接口 import 基础插件接口


class 用户候选HSP初筛插件(基础插件接口):
    """只补充计算字段，原始导入表始终保留不被覆盖。"""

    插件标识 = "用户候选HSP初筛"
    输入标识 = "用户导入_统一候选记录"
    输出标识 = "用户导入_HSP初筛记录"
    # SeeThrough Supplementary Data 1：BA 与 VA 的公开 HSP 参数。
    默认参照 = {
        "BA": {"参照体系": "BA", "HSP_dD": 18.6, "HSP_dP": 6.1, "HSP_dH": 12.4},
        "VA": {"参照体系": "VA", "HSP_dD": 18.8, "HSP_dP": 8.4, "HSP_dH": 11.9},
    }

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        输入标识 = str(数据上下文.get("HSP初筛输入标识", self.输入标识))
        输出标识 = str(数据上下文.get("HSP初筛输出标识", self.输出标识))
        候选 = 数据管理器.读取中间结果(输入标识).copy()
        参照 = dict(self.默认参照) | dict(数据上下文.get("HSP参照覆盖") or {})
        for 参照名, 参数 in 参照.items():
            距离列, 状态列, 原因列 = f"与{参照名}的Hansen距离", f"与{参照名}的HSP状态", f"与{参照名}的HSP原因"
            结果 = 候选.apply(lambda 行: HSP计算核心.评估(行, 参数), axis=1)
            候选[距离列] = 结果.map(lambda 值: 值["汉森距离_Ra"])
            候选[状态列] = 结果.map(lambda 值: 值["HSP状态"])
            候选[原因列] = 结果.map(lambda 值: 值["HSP原因"])
        候选["HSP初筛参数来源"] = "SeeThrough Supplementary Data 1（BA/VA 公开 HSP 参数）"
        数据管理器.保存中间结果(输出标识, 候选)
        return 候选
