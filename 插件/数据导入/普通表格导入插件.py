"""实际解析 SeeThrough 补充数据2，移除副表头和 C# 对照行。"""

from typing import Any

import pandas as pd

from 插件.插件接口 import 基础插件接口


class 普通表格导入插件(基础插件接口):
    插件标识 = "普通表格导入"
    文件名 = "SeeThrough补充数据2_1619个水相候选.xlsx"
    输出标识 = "补充数据2_统一候选记录"
    审计输出标识 = "补充数据2_导入清理审计"

    def 执行(self, 数据上下文: dict[str, Any]) -> pd.DataFrame:
        数据管理器 = 数据上下文["数据管理器"]
        原始表 = 数据管理器.读取论文表格(self.文件名)
        原始ID = 原始表["ID"].fillna("").astype(str)
        真实候选掩码 = 原始ID.str.fullmatch(r"#\d{4}")
        对照掩码 = 原始ID.str.fullmatch(r"C#\d{4}")
        副表头掩码 = 原始ID.eq("")
        候选表 = 原始表.loc[真实候选掩码].copy()
        候选编号 = 候选表["ID"].astype(str)
        重复编号 = 候选编号[候选编号.duplicated()].tolist()
        应有编号 = {f"#{编号:04d}" for 编号 in range(1, 1620)}
        实有编号 = set(候选编号)
        缺失编号 = sorted(应有编号 - 实有编号)
        多余编号 = sorted(实有编号 - 应有编号)
        空名称 = 候选表["Chemical Name"].fillna("").astype(str).str.strip().eq("")
        CAS格式异常 = ~候选表["Cas No."].fillna("").astype(str).str.fullmatch(r"\d{2,7}-\d{2}-\d")
        审计异常 = []
        if 重复编号:
            审计异常.append(f"重复候选编号：{','.join(重复编号)}")
        if 缺失编号:
            审计异常.append(f"缺失候选编号：{','.join(缺失编号)}")
        if 多余编号:
            审计异常.append(f"候选编号范围外：{','.join(多余编号)}")

        结果 = pd.DataFrame(
            {
                "候选编号": 候选表["ID"].astype(str),
                "论文ID": 候选表["ID"].astype(str),
                "论文_化学名称": 候选表["Chemical Name"].fillna("").astype(str),
                "论文_货号": 候选表["Cat. No."].fillna("").astype(str),
                "论文_CAS号": 候选表["Cas No."].fillna("").astype(str),
                "论文_水合能力平均值": pd.to_numeric(候选表["Hydration score"], errors="coerce"),
                "论文_水合能力标准差": pd.to_numeric(候选表["Unnamed: 5"], errors="coerce"),
                "论文_eRI": pd.to_numeric(候选表["eRI"], errors="coerce"),
                "论文_pH": pd.to_numeric(候选表["pH"], errors="coerce"),
                "论文_dD": pd.to_numeric(候选表["dD"], errors="coerce"),
                "论文_dP": pd.to_numeric(候选表["dP"], errors="coerce"),
                "论文_dH": pd.to_numeric(候选表["dH"], errors="coerce"),
                "论文数据来源": "SeeThrough Supplementary Data 2",
            }
        )
        审计 = pd.DataFrame(
            [
                {"项目": "原始数据行数", "数量": len(原始表), "说明": "Supplementary Data 2 工作表全部数据行"},
                {"项目": "副表头行", "数量": int(副表头掩码.sum()), "说明": "Hydration score 的 Average/SD 副表头"},
                {"项目": "C# 对照/非候选行", "数量": int(对照掩码.sum()), "说明": "water、PBS、TritonX-100 等 C# 控制条目"},
                {"项目": "清理后真实候选", "数量": len(结果), "说明": "严格匹配 #0001 至 #1619"},
                {"项目": "候选编号重复", "数量": len(重复编号), "说明": "; ".join(审计异常) or "无"},
                {"项目": "候选编号缺失", "数量": len(缺失编号), "说明": ",".join(缺失编号) or "无"},
                {"项目": "CAS格式异常", "数量": int(CAS格式异常.sum()), "说明": "仅审计；不因格式异常自动改写原始值"},
                {"项目": "化学名称为空", "数量": int(空名称.sum()), "说明": "仅审计；后续必要字段规则会保留原因"},
            ]
        )
        数据管理器.保存中间结果(self.审计输出标识, 审计)
        if 审计异常:
            raise ValueError("补充数据2导入校验失败：" + "；".join(审计异常))
        数据管理器.保存中间结果(self.输出标识, 结果)
        return 结果
