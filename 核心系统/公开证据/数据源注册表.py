from .数据源接口 import PublicDataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, PublicDataProvider] = {}

    def register(self, provider: PublicDataProvider) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"Provider already registered: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> PublicDataProvider:
        return self._providers[provider_id]

    def providers(self, provider_ids=None) -> tuple[PublicDataProvider, ...]:
        return tuple(self._providers.values()) if provider_ids is None else tuple(self.get(x) for x in provider_ids)
