"""数据校验入口；具体字段映射和业务规则留待后续实现。"""

from collections.abc import Mapping
from typing import Any

from 核心系统.数据格式定义 import 化学候选记录


def 校验化学候选记录(原始记录: Mapping[str, Any]) -> 化学候选记录:
    """仅校验统一数据格式，不执行筛选、评分或化学计算。"""
    return 化学候选记录.model_validate(dict(原始记录))
