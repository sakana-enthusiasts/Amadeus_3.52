"""CompTox查询接口：无密钥时可审计降级，绝不在代码中保存密钥。"""

import os
from typing import Any

import pandas as pd

from 设置.毒性设置 import CompTox密钥环境变量
from 插件.插件接口 import 基础插件接口


class CompTox接口状态插件(基础插件接口):
    """旧报告入口只显示配置状态；实际查询由公开证据聚合入口执行。"""
    插件标识 = "CompTox接口状态"
    输出标识 = "CompTox毒性查询状态"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        候选 = 数据管理器.读取筛选结果("补充数据2_规则筛选统一记录")
        候选 = 候选[候选["自动规则通过"].astype(str).str.lower().eq("true")]
        密钥 = os.getenv(CompTox密钥环境变量)
        状态 = "未配置" if not 密钥 else "已配置（公开证据入口可查询）"
        结果 = pd.DataFrame({"候选编号": 候选["候选编号"], "CAS": 候选["论文_CAS号"], "CompTox接口状态": 状态, "数据来源类型": "未查询", "说明": "本插件仅报告接口状态；实际查询请使用公开证据聚合入口。API密钥只从环境变量读取。"})
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果


# 兼容旧导入名；新流程和页面只使用“CompTox接口状态”。
CompTox查询插件 = CompTox接口状态插件
