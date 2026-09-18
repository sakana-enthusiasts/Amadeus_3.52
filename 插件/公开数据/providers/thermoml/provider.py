from dataclasses import replace

from 核心系统.公开证据.数据源接口 import PublicDataProvider
from 核心系统.公开证据.数据结构 import ProviderResult
from .client import ThermoMLClient
from .parser import ThermoMLParser


class ThermoMLProvider(PublicDataProvider):
    provider_id = "thermoml"

    def __init__(self, http):
        self.client = ThermoMLClient(http)
        self.parser = ThermoMLParser()

    def capabilities(self):
        return frozenset({"identity", "properties"})

    def resolve_identity(self, identity):
        url = identity.identifiers.get("thermoml_url")
        if not url:
            return ProviderResult("identity_missing", message="Supply an official ThermoML document URL; no fabricated compound search API")
        raw = self.client.document(url)
        if raw.status_code == 404:
            return ProviderResult("not_found", raw_record_ids=(raw.raw_record_id,))
        number = self.parser.resolve_org_number(raw, identity)
        return ProviderResult("ok", identity=replace(identity, identifiers={**identity.identifiers, "thermoml_org_num": number}),
                              raw_record_ids=(raw.raw_record_id,))

    def fetch_properties(self, identity):
        raw = self.client.document(identity.identifiers["thermoml_url"])
        evidence = self.parser.parse(raw, identity) if raw.status_code == 200 else []
        return ProviderResult("ok" if evidence else "not_found", tuple(evidence), identity, raw_record_ids=(raw.raw_record_id,))
