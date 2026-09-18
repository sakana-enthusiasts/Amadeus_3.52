"""各源复用限流、重试和 raw cache；不包含任何字段映射。"""

import json
import threading
import time

import requests


class CacheMissError(RuntimeError):
    pass


class CachedHTTPClient:
    _lock = threading.Lock()
    _last_request: dict[str, float] = {}

    def __init__(self, cache, source, parser_version, *, allow_network=False, use_cache=True,
                 requests_per_second=4, retries=3, request_get=None, sleeper=time.sleep):
        self.cache = cache
        self.source = source
        self.parser_version = parser_version
        self.allow_network = allow_network
        self.use_cache = use_cache
        self.interval = 1 / requests_per_second
        self.retries = retries
        self.request_get = request_get
        self.sleeper = sleeper

    def _throttle(self):
        with self._lock:
            delay = self.interval - (time.monotonic() - self._last_request.get(self.source, 0))
            if delay > 0:
                self.sleeper(delay)
            self._last_request[self.source] = time.monotonic()

    def get(self, url, source_record_id="", *, headers=None):
        if self.use_cache:
            cached = self.cache.get(self.source, url, ignore_age=not self.allow_network)
            if cached:
                return cached
        if not self.allow_network:
            raise CacheMissError("Offline raw cache miss")
        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                response = (self.request_get or requests.get)(url, timeout=25, **({"headers": headers} if headers else {}))
            except requests.RequestException:
                if attempt == self.retries:
                    raise RuntimeError("Network request failed; check source availability") from None
                self.sleeper(min(2 ** attempt, 30))
                continue
            body = getattr(response, "text", None)
            if not isinstance(body, str):
                body = json.dumps(response.json(), ensure_ascii=False)
            raw = self.cache.save(self.source, url, str(source_record_id), response.status_code, body, self.parser_version)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                retry_after = getattr(response, "headers", {}).get("Retry-After", "")
                delay = float(retry_after) if str(retry_after).replace(".", "", 1).isdigit() else 2 ** attempt
                self.sleeper(min(delay, 30))
                continue
            if response.status_code not in {200, 404}:
                raise RuntimeError(f"Source HTTP status {response.status_code}; raw response retained")
            return raw
        raise RuntimeError("Retry limit reached")
