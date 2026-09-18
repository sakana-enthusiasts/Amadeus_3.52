from dataclasses import replace
import re

from 核心系统.公开证据.数据源接口 import PublicDataProvider
from 核心系统.公开证据.数据结构 import ProviderResult
from .client import WebBookClient
from .mapping import NIST_INDIVIDUAL_TYPES
from .parser import WebBookParser


class NISTProvider(PublicDataProvider):
    provider_id = "nist"

    def __init__(self, http):
        self.client = WebBookClient(http)
        self.parser = WebBookParser()

    def capabilities(self):
        return frozenset({"identity", "properties"})

    def resolve_identity(self, identity):
        record_id = identity.identifiers.get("nist_id")
        cas = identity.identifiers.get("cas", "")
        if not record_id and re.fullmatch(r"\d{2,7}-\d{2}-\d", cas):
            record_id = "C" + cas.replace("-", "")
        if not record_id:
            return ProviderResult("identity_missing", message="WebBook requires an observed CAS or NIST record ID")
        if not re.fullmatch(r"[A-Za-z0-9]+", record_id):
            return ProviderResult("identity_conflict", message="Invalid NIST record ID")
        return ProviderResult("ok", identity=replace(identity, identifiers={**identity.identifiers, "nist_id": record_id}))

    def fetch_properties(self, identity):
        raw = self.client.properties(identity.identifiers["nist_id"])
        raw_ids = [raw.raw_record_id]
        evidence = self.parser.parse(raw, identity) if raw.status_code == 200 else []
        errors = []
        # WebBook 首页常给平均值；另外取明示的单条原始测量列表，仍保留平均值。
        for prop, individual_type in NIST_INDIVIDUAL_TYPES.items():
            if any(e.property_id == prop and any(f"Type={individual_type}" in link for link in e.reference["links"]) for e in evidence):
                try:
                    item = self.client.properties(identity.identifiers["nist_id"], individual_type)
                    raw_ids.append(item.raw_record_id)
                    if item.status_code == 200:
                        evidence.extend(self.parser.parse(item, identity))
                except (RuntimeError, ValueError) as error:
                    errors.append(str(error))
        return ProviderResult("partial" if errors else "ok" if evidence else "not_found", tuple(evidence), identity,
                              "; ".join(errors), tuple(raw_ids))
