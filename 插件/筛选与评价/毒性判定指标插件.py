"""将独立毒性证据表转换为规则引擎可用的指标记录。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from 核心系统.通用规则引擎 import 毒性判定指标插件 as 指标计算器
from 插件.插件接口 import 基础插件接口


class 毒性判定指标规则插件(基础插件接口):
    插件标识 = "毒性判定指标"
    输入标识 = "毒性原始证据"
    输出标识 = "毒性判定指标"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        run_id = str(数据上下文.get("运行编号") or getattr(数据管理器, "当前运行编号", "") or "legacy")
        输入标识 = str(数据上下文.get("毒性证据输入标识", self.输入标识))
        try:
            证据 = 数据管理器.读取毒性结果(输入标识)
        except (FileNotFoundError, AttributeError):
            try:
                证据 = 数据管理器.读取筛选结果(输入标识)
            except FileNotFoundError:
                证据 = pd.DataFrame()
        结果 = 指标计算器().执行(run_id, 证据)
        if hasattr(数据管理器, "保存毒性结果"):
            数据管理器.保存毒性结果(self.输出标识, 结果)
        else:
            数据管理器.保存筛选结果(self.输出标识, 结果)
        return 结果
