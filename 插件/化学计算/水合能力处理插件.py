"""保留实验水合评分及其缺失状态，不用其他描述符替代。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 水合能力处理插件(基础插件接口):
    插件标识 = "水合能力处理"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        原始 = 数据上下文.get("成分")
        成分 = 原始.copy() if isinstance(原始, pd.DataFrame) else pd.DataFrame([] if 原始 is None else 原始)
        if 成分.empty:
            return pd.DataFrame(columns=["成分键", "实验水合评分", "水合数据状态"])
        if "实验水合评分" not in 成分:
            成分["实验水合评分"] = pd.NA
        成分["实验水合评分"] = pd.to_numeric(成分["实验水合评分"], errors="coerce")
        成分["水合数据状态"] = 成分["实验水合评分"].map(lambda 值: "已有实验水合评分" if pd.notna(值) else "待补实验水合评分")
        return 成分[[字段 for 字段 in ("成分键", "候选编号", "实验水合评分", "水合数据状态") if 字段 in 成分]].copy()
