"""为用户候选流程提供 run_id 隔离的数据管理器。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import uuid4

import pandas as pd

from .数据管理接口 import 文件数据访问管理器


class 运行数据管理器(文件数据访问管理器):
    """兼容原有数据接口，同时让激活运行的全部产物进入独立目录。"""

    def __init__(self, 项目根目录: Path) -> None:
        super().__init__(项目根目录)
        self.运行记录目录 = self.项目根目录 / "数据" / "运行记录"
        self._当前运行编号: str | None = None

    @staticmethod
    def 安全文件名(文件名: str) -> str:
        原始 = str(文件名 or "")
        标准化 = 原始.replace("\\", "/")
        if not 标准化 or 标准化.startswith("/") or ":" in 标准化 or ".." in standard_parts(标准化):
            raise ValueError("上传文件名不能包含路径、盘符或父目录")
        名称 = PureWindowsPath(标准化).name
        if 名称 in {"", ".", ".."} or 名称 != 标准化:
            raise ValueError("上传文件名必须是单个安全文件名")
        return 名称

    def 创建运行(self, 应用配置: str, 输入文件名: str, 元数据: dict[str, Any] | None = None) -> str:
        文件名 = self.安全文件名(输入文件名)
        run_id = f"run_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:10]}"
        根目录 = self.运行记录目录 / run_id
        for 子目录 in ("用户导入", "中间结果", "筛选结果", "毒性结果", "模型结果", "导出结果", "属性记录", "规则结果"):
            目录 = 根目录 / 子目录
            self.确认目标可写入(目录 / ".gitkeep")
            目录.mkdir(parents=True, exist_ok=True)
        元数据记录 = {
            "run_id": run_id,
            "创建时间": datetime.now(timezone.utc).isoformat(),
            "应用配置": 应用配置,
            "输入文件名": 文件名,
            "元数据": 元数据 or {},
        }
        元数据路径 = 根目录 / "运行元数据.json"
        self.确认目标可写入(元数据路径)
        元数据路径.write_text(json.dumps(元数据记录, ensure_ascii=False, indent=2), encoding="utf-8")
        self._当前运行编号 = run_id
        return run_id

    def 激活运行(self, run_id: str) -> None:
        根目录 = self.运行记录目录 / str(run_id)
        if not (根目录 / "运行元数据.json").is_file():
            raise FileNotFoundError(f"未找到运行编号：{run_id}")
        self._当前运行编号 = str(run_id)

    @property
    def 当前运行编号(self) -> str | None:
        return self._当前运行编号

    def 运行目录(self, run_id: str | None = None) -> Path:
        有效编号 = run_id or self._当前运行编号
        if not 有效编号:
            raise RuntimeError("当前没有激活的运行编号")
        目录 = (self.运行记录目录 / 有效编号).resolve()
        if self.运行记录目录.resolve() not in 目录.parents:
            raise ValueError("运行目录不在允许范围内")
        return 目录

    def _运行或旧目录(self, 子目录: str, 旧目录: Path, run_id: str | None = None) -> Path:
        有效编号 = run_id or self._当前运行编号
        return self.运行目录(有效编号) / 子目录 if 有效编号 else 旧目录

    def 保存中间结果(self, 数据标识: str, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("中间结果", self.中间结果目录, run_id), 数据标识, 数据)

    def 读取中间结果(self, 数据标识: str, run_id: str | None = None) -> pd.DataFrame:
        return self._读取表格(self._运行或旧目录("中间结果", self.中间结果目录, run_id), 数据标识)

    def 保存最终结果(self, 数据标识: str, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("模型结果", self.模型结果目录, run_id), 数据标识, 数据)

    def 保存筛选结果(self, 数据标识: str, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("筛选结果", self.筛选结果目录, run_id), 数据标识, 数据)

    def 读取筛选结果(self, 数据标识: str, run_id: str | None = None) -> pd.DataFrame:
        return self._读取表格(self._运行或旧目录("筛选结果", self.筛选结果目录, run_id), 数据标识)

    def 读取最终结果(self, 数据标识: str, run_id: str | None = None) -> pd.DataFrame:
        模型目录 = self._运行或旧目录("模型结果", self.模型结果目录, run_id)
        try:
            return self._读取表格(模型目录, 数据标识)
        except FileNotFoundError:
            return self.读取筛选结果(数据标识, run_id)

    def 结果存在(self, 数据标识: str, 是否最终结果: bool = False, run_id: str | None = None) -> bool:
        if 是否最终结果:
            try:
                self.读取最终结果(数据标识, run_id)
                return True
            except FileNotFoundError:
                return False
        try:
            self.读取中间结果(数据标识, run_id)
            return True
        except FileNotFoundError:
            return False

    def 保存毒性结果(self, 数据标识: str, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("毒性结果", self.筛选结果目录, run_id), 数据标识, 数据)

    def 读取毒性结果(self, 数据标识: str, run_id: str | None = None) -> pd.DataFrame:
        return self._读取表格(self._运行或旧目录("毒性结果", self.筛选结果目录, run_id), 数据标识)

    def 保存属性记录(self, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("属性记录", self.中间结果目录, run_id), "属性记录", 数据)

    def 读取属性记录(self, run_id: str | None = None) -> pd.DataFrame:
        return self._读取表格(self._运行或旧目录("属性记录", self.中间结果目录, run_id), "属性记录")

    def 保存规则结果(self, 数据: pd.DataFrame, run_id: str | None = None) -> Path:
        return self._保存表格(self._运行或旧目录("规则结果", self.筛选结果目录, run_id), "规则执行记录", 数据)

    def 保存导出报告(self, 文件名: str, 内容: bytes, run_id: str | None = None) -> Path:
        安全名称 = self.安全文件名(文件名)
        目录 = self._运行或旧目录("导出结果", self.导出结果目录, run_id)
        路径 = (目录 / 安全名称).resolve()
        if 目录.resolve() not in 路径.parents:
            raise ValueError("导出目标不在运行目录内")
        self.确认目标可写入(路径)
        目录.mkdir(parents=True, exist_ok=True)
        路径.write_bytes(内容)
        return 路径

    def 保存用户导入原始文件(self, 文件名: str, 内容: bytes, run_id: str | None = None) -> Path:
        安全名称 = self.安全文件名(文件名)
        目录 = self._运行或旧目录("用户导入", self.用户导入数据目录, run_id)
        路径 = (目录 / 安全名称).resolve()
        if 目录.resolve() not in 路径.parents:
            raise ValueError("上传目标不在用户导入目录内")
        self.确认目标可写入(路径)
        目录.mkdir(parents=True, exist_ok=True)
        路径.write_bytes(内容)
        return 路径


def standard_parts(路径: str) -> tuple[str, ...]:
    """使用 POSIX 分隔符检查上传名，避免宿主平台的差异。"""
    return tuple(部分 for 部分 in 路径.split("/") if 部分)
