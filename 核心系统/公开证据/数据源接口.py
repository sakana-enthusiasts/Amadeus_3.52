from abc import ABC, abstractmethod

from .数据结构 import CompoundIdentity, ProviderResult


class PublicDataProvider(ABC):
    provider_id: str

    @abstractmethod
    def capabilities(self) -> frozenset[str]:
        raise NotImplementedError

    @abstractmethod
    def resolve_identity(self, identity: CompoundIdentity) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    def fetch_properties(self, identity: CompoundIdentity) -> ProviderResult:
        raise NotImplementedError

    def fetch_hazard(self, identity: CompoundIdentity) -> ProviderResult:
        return ProviderResult("unsupported", message="hazard capability unsupported")

    def fetch_bioactivity(self, identity: CompoundIdentity) -> ProviderResult:
        return ProviderResult("unsupported", message="bioactivity capability unsupported")

    def fetch_toxicokinetics(self, identity: CompoundIdentity) -> ProviderResult:
        return ProviderResult("unsupported", message="toxicokinetics capability unsupported")
