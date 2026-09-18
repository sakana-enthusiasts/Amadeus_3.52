"""公开数据契约；不依赖具体数据库、功能插件或计算模型。"""

from .数据结构 import CompoundIdentity, PropertyEvidence, EvidenceRequest, ResolvedProperty, ProviderResult
from .数据源注册表 import ProviderRegistry
from .证据选择器 import EvidenceResolver
from .证据存储接口 import EvidenceRepository

__all__ = ["CompoundIdentity", "PropertyEvidence", "EvidenceRequest", "ResolvedProperty",
           "ProviderResult", "ProviderRegistry", "EvidenceResolver", "EvidenceRepository"]
