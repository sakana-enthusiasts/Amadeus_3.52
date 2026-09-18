"""保存人工身份审核决定；不直接导入或调用其他业务插件。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 人工身份确认插件(基础插件接口):
    插件标识 = "人工身份确认"
    确认文件 = "人工身份确认记录.csv"
    缓存文件 = "化合物身份缓存.csv"
    冲突标识 = "化合物身份冲突表"

    @staticmethod
    def _缓存主键(记录: dict[str, Any] | pd.Series) -> str:
        return "|".join(str(记录.get(字段, "")).strip().lower() for 字段 in ("CAS号", "货号", "化学名称"))

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        候选编号 = str(数据上下文["候选编号"])
        操作 = str(数据上下文["操作"])
        CID = str(数据上下文.get("PubChem CID", "")).strip()
        SMILES = str(数据上下文.get("Isomeric SMILES", "")).strip()
        说明 = str(数据上下文.get("说明", "")).strip()
        if 操作 == "确认CID" and not CID:
            raise ValueError("确认CID时必须填写CID")
        if 操作 == "手工输入结构" and not SMILES:
            raise ValueError("手工输入结构时必须填写可审核的SMILES")
        输出标识 = str(数据上下文.get("身份输出标识", "用户导入_化合物身份映射"))
        try:
            映射 = 数据管理器.读取中间结果(输出标识).copy()
        except FileNotFoundError as 错误:
            raise FileNotFoundError(f"未找到当前运行的身份映射：{输出标识}") from 错误
        命中 = 映射[映射["候选编号"].astype(str).eq(候选编号)]
        if 命中.empty:
            raise ValueError(f"未找到候选：{候选编号}")
        索引 = 命中.index[0]
        状态 = "人工确认" if 操作 in {"确认CID", "手工输入结构"} else "无法确认"
        映射.loc[索引, "匹配状态"] = 状态
        映射.loc[索引, "自动匹配或人工确认"] = "人工确认"
        映射.loc[索引, "冲突说明"] = 说明 or 操作
        if CID:
            映射.loc[索引, "PubChem CID"] = CID
        if SMILES:
            映射.loc[索引, "Isomeric SMILES"] = SMILES
            映射.loc[索引, "Canonical SMILES"] = SMILES
        映射.loc[索引, "查询时间"] = datetime.now(timezone.utc).isoformat()
        数据管理器.保存中间结果(输出标识, 映射)
        记录 = 映射.loc[索引].to_dict() | {
            "人工操作": 操作,
            "人工确认时间": datetime.now(timezone.utc).isoformat(),
            "人工确认说明": 说明,
        }
        try:
            历史 = 数据管理器.读取软件数据库表格(self.确认文件)
        except FileNotFoundError:
            历史 = pd.DataFrame()
        历史 = pd.concat([历史, pd.DataFrame([记录])], ignore_index=True)
        历史 = 历史.drop_duplicates(subset=["候选编号", "人工操作"], keep="last")
        数据管理器.保存软件数据库表格(self.确认文件, 历史)
        try:
            缓存 = 数据管理器.读取软件数据库表格(self.缓存文件)
        except FileNotFoundError:
            缓存 = pd.DataFrame()
        记录["缓存主键"] = self._缓存主键(记录)
        缓存 = pd.concat([缓存, pd.DataFrame([记录])], ignore_index=True)
        缓存["缓存主键"] = 缓存.apply(self._缓存主键, axis=1)
        缓存 = 缓存.drop_duplicates(subset=["缓存主键"], keep="last")
        数据管理器.保存软件数据库表格(self.缓存文件, 缓存)
        try:
            冲突 = 数据管理器.读取筛选结果(self.冲突标识)
        except FileNotFoundError:
            冲突 = pd.DataFrame()
        if not 冲突.empty and "候选编号" in 冲突:
            掩码 = 冲突["候选编号"].astype(str).eq(候选编号)
            冲突.loc[掩码, "人工确认状态"] = "已确认" if 状态 == "人工确认" else "无法确认"
            冲突.loc[掩码, "当前采用值"] = CID or ("手工SMILES" if SMILES else "不采用")
            冲突.loc[掩码, "采用理由"] = 说明 or 操作
            数据管理器.保存筛选结果(self.冲突标识, 冲突)
        return pd.DataFrame([记录])
