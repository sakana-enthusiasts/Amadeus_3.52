"""运行记录接口；具体日志格式与持久化策略尚未实现。"""

import logging


def 获取日志记录器(名称: str) -> logging.Logger:
    """返回标准日志记录器，不在本阶段写入业务运行记录。"""
    return logging.getLogger(名称)
