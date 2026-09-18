"""旧导入名兼容外观；新流程只注册公开证据聚合插件。"""

import requests  # 保留旧调用者注入 requests.get 的入口。

from 核心系统.公开证据.数据结构 import CompoundIdentity
from 核心系统.公开证据.原始响应缓存 import RawResponseCache
from 插件.公开数据.公开证据聚合插件 import 公开证据聚合插件
from 插件.公开数据.GHS兼容输出 import format_ghs
from 插件.公开数据.providers.网络客户端 import CachedHTTPClient
from 插件.公开数据.providers.pubchem import PubChemProvider
from 插件.公开数据.providers.pubchem.parser import PARSER_VERSION, text_values


class PubChem查询插件(公开证据聚合插件):
    """供旧脚本导入；不再实现独立网络、身份或存储逻辑。"""
    输出标识 = "PubChem_GHS毒性证据"
    毒理公开输出标识 = "毒理公开证据_PubChemGHS"
    毒理公开日志标识 = "毒理公开查询日志"
    毒理公开原始响应标识 = "毒理公开原始响应_PubChemGHS"

    @staticmethod
    def _提取文本(value):
        return list(text_values(value))

    def _GHS(self, CID):
        cache = RawResponseCache()
        try:
            provider = PubChemProvider(CachedHTTPClient(cache, "pubchem", PARSER_VERSION, allow_network=True))
            identity = CompoundIdentity("legacy", identifiers={"pubchem_cid": str(CID)})
            result = provider.fetch_hazard(identity)
            raw = cache.records("pubchem")[-1]
            return (format_ghs(result.evidence, raw.body), "") if result.evidence else ({}, "未找到GHS条目")
        finally:
            cache.close()
