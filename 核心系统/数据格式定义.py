"""跨插件共用的数据格式接口；字段参考 SeeThrough 补充数据表。"""

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class 化学候选记录(BaseModel):
    """候选化合物的统一字段，允许后续数据源携带额外原始字段。"""

    model_config = ConfigDict(extra="allow")

    候选标识: str | None = Field(
        default=None, validation_alias=AliasChoices("候选标识", "ID"), description="论文或用户提供的候选 ID"
    )
    化学名称: str | None = Field(default=None, validation_alias=AliasChoices("化学名称", "Chemical Name"))
    货号: str | None = Field(default=None, validation_alias=AliasChoices("货号", "Cat. No."))
    CAS号: str | None = Field(default=None, validation_alias=AliasChoices("CAS号", "Cas No."))
    数据来源: str | None = None
    估算折射率: float | None = Field(default=None, validation_alias=AliasChoices("估算折射率", "eRI", "eRI (RI*)"))
    测量折射率: float | None = Field(default=None, validation_alias=AliasChoices("测量折射率", "RI"))
    水合能力均值: float | None = Field(default=None, validation_alias=AliasChoices("水合能力均值", "Hydration score"))
    水合能力标准差: float | None = Field(default=None, validation_alias=AliasChoices("水合能力标准差", "Unnamed: 5"))
    pH值: float | None = Field(default=None, validation_alias=AliasChoices("pH值", "pH"))
    Hansen色散参数_dD: float | None = Field(default=None, validation_alias=AliasChoices("Hansen色散参数_dD", "dD"))
    Hansen极性参数_dP: float | None = Field(default=None, validation_alias=AliasChoices("Hansen极性参数_dP", "dP"))
    Hansen氢键参数_dH: float | None = Field(default=None, validation_alias=AliasChoices("Hansen氢键参数_dH", "dH"))
    与BA混合折射率: float | None = Field(default=None, validation_alias=AliasChoices("与BA混合折射率", "RI with BA"))
    与VA混合折射率: float | None = Field(default=None, validation_alias=AliasChoices("与VA混合折射率", "RI with VA"))


class 数据批次(BaseModel):
    """导入、处理中间结果与导出结果的通用元数据。"""

    批次标识: str
    数据类型: str
    数据来源: str | None = None
    附加信息: dict[str, Any] = Field(default_factory=dict)


class 毒性证据记录(BaseModel):
    """一条可追溯毒性证据；不同物种、途径和终点必须作为不同记录保存。"""

    model_config = ConfigDict(extra="allow")
    候选编号: str
    CAS: str | None = None
    PubChem_CID: str | None = Field(default=None, validation_alias=AliasChoices("PubChem CID", "PubChem_CID"))
    InChIKey: str | None = None
    化合物形式: str | None = None
    毒性终点: str
    物种: str | None = None
    细胞或组织来源: str | None = None
    给药途径: str | None = None
    剂量: str | None = None
    剂量单位: str | None = None
    暴露时长: str | None = None
    观察时长: str | None = None
    结果: str | None = None
    实验值或预测值: str
    原始数据_数据库汇总或模型预测: str | None = Field(default=None, validation_alias=AliasChoices("原始数据、数据库汇总或模型预测", "原始数据_数据库汇总或模型预测"))
    数据来源: str | None = None
    原始来源链接或编号: str | None = None
    可信度: str | None = None
    数据是否与当前实验条件匹配: str | None = None
    备注: str | None = None
