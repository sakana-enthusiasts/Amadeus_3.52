from dataclasses import replace
import re

from 核心系统.公开证据.数据源接口 import PublicDataProvider
from 核心系统.公开证据.数据结构 import ProviderResult
from 核心系统.公开证据.身份标准化 import standardize_identity
from .client import CTXClient, MissingAPIKeyError
from .parser import CTXParser, records


class CompToxProvider(PublicDataProvider):
    provider_id = "comptox"

    def __init__(self, http, api_key=None):
        self.client = CTXClient(http, api_key)
        self.parser = CTXParser()

    def capabilities(self):
        return frozenset({"identity", "properties", "hazard", "bioactivity", "toxicokinetics"})

    def resolve_identity(self, identity):
        dtxsid = identity.identifiers.get("dtxsid", "")
        if dtxsid:
            return ProviderResult("ok" if re.fullmatch(r"DTXSID\d+", dtxsid) else "identity_conflict", identity=identity)
        query = identity.inchikey or identity.identifiers.get("cas") or identity.identifiers.get("name")
        if not query:
            return ProviderResult("identity_missing", message="No DSSTox lookup identity")
        try:
            raw = self.client.resolve(query)
        except MissingAPIKeyError as error:
            return ProviderResult("unconfigured", message=str(error))
        hits = records(raw.json()) if raw.status_code == 200 else []
        ids = {x["dtxsid"] for x in hits if x.get("dtxsid")}
        if len(ids) != 1:
            return ProviderResult("identity_conflict" if ids else "not_found", message="No unique DTXSID",
                                  raw_record_ids=(raw.raw_record_id,))
        hit = next(x for x in hits if x.get("dtxsid") in ids)
        if identity.inchikey and hit.get("inchikey") and hit["inchikey"] != identity.inchikey:
            return ProviderResult("identity_conflict", message="DSSTox identity conflicts with observed form")
        resolved = replace(identity, identifiers={**identity.identifiers, "dtxsid": next(iter(ids))})
        if not resolved.observed_structure and hit.get("smiles"):
            resolved = standardize_identity(replace(resolved, observed_structure=hit["smiles"]))
        return ProviderResult("ok", identity=resolved, raw_record_ids=(raw.raw_record_id,))

    def _domains(self, identity, domains):
        evidence, raw_ids, errors = [], [], []
        unconfigured = False
        for domain in domains:
            try:
                raw = self.client.domain(domain, identity.identifiers["dtxsid"])
                raw_ids.append(raw.raw_record_id)
                if raw.status_code == 200:
                    evidence.extend(self.parser.parse(raw, identity, domain))
            except MissingAPIKeyError as error:
                unconfigured = True
                errors.append(f"{domain}: {error}")
            except ValueError:
                return ProviderResult("identity_conflict", message=f"CTX {domain} response conflicts with identity or schema",
                                      raw_record_ids=tuple(raw_ids))
            except RuntimeError as error:
                errors.append(f"{domain}: {error}")
        return ProviderResult("partial" if errors and evidence else "unconfigured" if unconfigured else "error" if errors else "ok" if evidence else "not_found",
                              tuple(evidence), identity, "; ".join(errors), tuple(raw_ids))

    def fetch_properties(self, identity):
        return self._domains(identity, ("chemistry", "experimental", "predicted"))

    def fetch_hazard(self, identity):
        return self._domains(identity, ("toxval", "toxref"))

    def fetch_bioactivity(self, identity):
        return self._domains(identity, ("bioactivity",))

    def fetch_toxicokinetics(self, identity):
        return self._domains(identity, ("toxicokinetics",))
