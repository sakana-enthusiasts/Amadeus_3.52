from dataclasses import replace

from 核心系统.公开证据.数据源接口 import PublicDataProvider
from 核心系统.公开证据.数据结构 import ProviderResult
from 核心系统.公开证据.身份标准化 import standardize_identity
from .client import PUGRestClient, PUGViewClient
from .identity import IdentityResolver
from .parser import PUGRestParser, PUGViewParser


class PubChemProvider(PublicDataProvider):
    provider_id = "pubchem"

    def __init__(self, http):
        self.rest = PUGRestClient(http)
        self.view = PUGViewClient(http)
        self.identity_resolver = IdentityResolver(self.rest)
        self.rest_parser = PUGRestParser()
        self.view_parser = PUGViewParser()

    def capabilities(self):
        return frozenset({"identity", "properties", "hazard"})

    def resolve_identity(self, identity):
        return self.identity_resolver.resolve(identity)

    def fetch_properties(self, identity):
        cid = identity.identifiers["pubchem_cid"]
        evidence, raw_ids, errors = [], [], []
        try:
            raw = self.rest.properties(cid)
            raw_ids.append(raw.raw_record_id)
            if raw.status_code == 200:
                evidence.extend(self.rest_parser.parse(raw, identity))
                records = raw.json().get("PropertyTable", {}).get("Properties", [])
                if records and not identity.observed_structure:
                    record = records[0]
                    observed = record.get("SMILES", record.get("IsomericSMILES", record.get("CanonicalSMILES", record.get("ConnectivitySMILES", ""))))
                    identity = standardize_identity(replace(identity, observed_structure=observed, inchikey=record.get("InChIKey", "")))
                    evidence = [replace(e, observed_structure=identity.observed_structure,
                                        standardized_parent_structure=identity.standardized_parent_structure) for e in evidence]
        except ValueError:
            return ProviderResult("identity_conflict", message="Computed record conflicts with observed identity", raw_record_ids=tuple(raw_ids))
        except RuntimeError as error:
            errors.append(str(error))
        try:
            index = self.view.index(cid)
            raw_ids.append(index.raw_record_id)
            headings = self.view_parser.discover(index) if index.status_code == 200 else ()
        except (RuntimeError, ValueError) as error:
            errors.append(str(error))
            headings = ()
        for heading in headings:
            try:
                raw = self.view.heading(cid, heading)
                raw_ids.append(raw.raw_record_id)
                if raw.status_code == 200:
                    evidence.extend(self.view_parser.parse(raw, identity, heading))
            except (RuntimeError, ValueError) as error:
                errors.append(f"{heading}: {error}")
        return ProviderResult("partial" if errors and evidence else "error" if errors else "ok" if evidence else "not_found",
                              tuple(evidence), identity, "; ".join(errors), tuple(raw_ids))

    def fetch_hazard(self, identity):
        raw = self.view.heading(identity.identifiers["pubchem_cid"], "GHS Classification")
        evidence = self.view_parser.parse_hazard(raw, identity) if raw.status_code == 200 else []
        return ProviderResult("ok" if evidence else "not_found", tuple(evidence), identity,
                              raw_record_ids=(raw.raw_record_id,), cache_hit=raw.cache_hit)
