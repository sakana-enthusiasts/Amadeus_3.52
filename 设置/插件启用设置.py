"""Amadeus 的可选功能开关。

核心计算不依赖本模块。结果可视化只读取已经落盘的结果，因此在开发
新流程或调整输出字段时可以临时关闭，避免界面兼容性影响算法验收。
"""

from __future__ import annotations

import os


def _读取布尔环境变量(名称: str, 默认值: bool) -> bool:
    """读取可选功能开关；未设置时使用演示版的默认配置。"""
    值 = os.getenv(名称)
    if 值 is None:
        return 默认值
    return 值.strip().lower() in {"1", "true", "yes", "on"}


def 启用结果可视化() -> bool:
    """是否生成并展示筛选结果图表。

    默认开启，以便 Demo 开箱可用。开发期间可用
    ``AMADEUS_ENABLE_RESULT_VISUALIZATION=0`` 暂时关闭；关闭不会影响
    筛选、报告导出和原始结果保存。
    """
    return _读取布尔环境变量("AMADEUS_ENABLE_RESULT_VISUALIZATION", True)
