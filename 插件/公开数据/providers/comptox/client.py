import os
from urllib.parse import quote

from .mapping import DOMAIN_PATHS


class MissingAPIKeyError(RuntimeError):
    pass


class CTXClient:
    base = "https://comptox.epa.gov/ctx-api/"

    def __init__(self, http, api_key=None):
        self.http = http
        self._api_key = api_key

    def _get(self, path, record_id=""):
        # 密钥只进入请求头，不进入 URL、缓存、日志或异常文本。
        key = self._api_key or os.getenv("COMPTOX_API_KEY", "")
        if self.http.allow_network and not key:
            cached = self.http.cache.get("comptox", self.base + path) if self.http.use_cache else None
            if cached:
                return cached
            raise MissingAPIKeyError("CompTox API key is not configured")
        return self.http.get(self.base + path, record_id, headers={"x-api-key": key, "Accept": "application/json"})

    def resolve(self, query):
        return self._get("chemical/search/equal/" + quote(query, safe=""))

    def domain(self, domain, dtxsid):
        return self._get(DOMAIN_PATHS[domain].format(id=quote(dtxsid, safe="")), dtxsid)
