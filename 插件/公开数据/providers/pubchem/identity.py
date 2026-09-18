from dataclasses import replace
import re

from 核心系统.公开证据.数据结构 import ProviderResult


class IdentityResolver:
    def __init__(self, rest):
        self.rest = rest

    def resolve(self, identity):
        cid = identity.identifiers.get("pubchem_cid", "").strip()
        if cid:
            if not re.fullmatch(r"[1-9]\d*", cid):
                return ProviderResult("identity_conflict", message="Invalid CID")
            return ProviderResult("ok", identity=identity)
        queries = [("inchikey", identity.inchikey), ("smiles", identity.observed_structure),
                   ("name", identity.identifiers.get("cas", "")), ("name", identity.identifiers.get("name", ""))]
        namespace, query = next(((ns, value) for ns, value in queries if value), ("", ""))
        if not query:
            return ProviderResult("identity_missing", message="No observed identity available")
        raw = self.rest.resolve(namespace, query)
        if raw.status_code == 404:
            return ProviderResult("not_found", raw_record_ids=(raw.raw_record_id,))
        cids = sorted({str(x) for x in raw.json().get("IdentifierList", {}).get("CID", [])})
        if len(cids) != 1:
            return ProviderResult("identity_conflict" if cids else "not_found", message="No unique CID; no automatic selection",
                                  raw_record_ids=(raw.raw_record_id,))
        return ProviderResult("ok", identity=replace(identity, identifiers={**identity.identifiers, "pubchem_cid": cids[0]}),
                              raw_record_ids=(raw.raw_record_id,))
