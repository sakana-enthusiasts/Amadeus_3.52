from 核心系统.公开证据.数据源注册表 import ProviderRegistry
from .providers.网络客户端 import CachedHTTPClient
from .providers.pubchem import PubChemProvider
from .providers.pubchem.parser import PARSER_VERSION as PUBCHEM_VERSION
from .providers.comptox import CompToxProvider
from .providers.comptox.parser import PARSER_VERSION as COMPTOX_VERSION
from .providers.nist import NISTProvider
from .providers.nist.parser import PARSER_VERSION as NIST_VERSION
from .providers.thermoml import ThermoMLProvider
from .providers.thermoml.parser import PARSER_VERSION as THERMOML_VERSION


def create_registry(cache, *, allow_network=False, use_cache=True):
    registry = ProviderRegistry()
    for provider_class, version in ((PubChemProvider, PUBCHEM_VERSION), (CompToxProvider, COMPTOX_VERSION),
                                    (NISTProvider, NIST_VERSION), (ThermoMLProvider, THERMOML_VERSION)):
        http = CachedHTTPClient(cache, provider_class.provider_id, version,
                                allow_network=allow_network, use_cache=use_cache)
        registry.register(provider_class(http))
    return registry
