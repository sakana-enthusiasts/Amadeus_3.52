"""流程唯一公开数据功能入口。Provider、Repository、Resolver 均可注入替换。"""

from pathlib import Path
from dataclasses import replace

import pandas as pd

from 核心系统.公开证据.数据结构 import CompoundIdentity, EvidenceRequest, ProviderResult, ResolvedProperty
from 核心系统.公开证据.身份标准化 import standardize_identity
from 核心系统.公开证据.原始响应缓存 import RawResponseCache
from 核心系统.公开证据.证据存储 import SQLiteEvidenceRepository, DuckDBEvidenceRepository, ParquetEvidenceRepository
from 核心系统.公开证据.证据选择器 import EvidenceResolver
from 插件.插件接口 import 基础插件接口
from .默认数据源 import create_registry
from .GHS兼容输出 import candidates_for_legacy, save_legacy
from .缓存迁移 import import_legacy_ghs


def _value(row, *names, default=""):
    for name in names:
        value = row.get(name)
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value).strip()
    return default


def candidate_identity(row, *, standardize=True):
    if isinstance(row, CompoundIdentity):
        return standardize_identity(row) if standardize else row
    identifier_names = {"pubchem_cid": ("pubchem_cid", "PubChem CID"), "dtxsid": ("dtxsid", "DTXSID"),
                        "cas": ("cas", "CAS", "CAS号", "论文_CAS号", "原始CAS"),
                        "name": ("name", "化学名称", "原始名称"), "nist_id": ("nist_id",),
                        "thermoml_url": ("thermoml_url",), "thermoml_org_num": ("thermoml_org_num",)}
    identifiers = {key: _value(row, *names) for key, names in identifier_names.items() if _value(row, *names)}
    identifiers.update(row.get("identifiers") or {})
    compound_id = _value(row, "compound_id", "候选编号")
    if not compound_id:
        raise ValueError("Each public candidate requires a stable compound_id / 候选编号")
    identity = CompoundIdentity(compound_id,
        chemical_form=_value(row, "chemical_form", "化合物形式", default="unspecified"),
        observed_structure=_value(row, "observed_structure", "Isomeric SMILES", "Canonical SMILES", "SMILES"),
        standardized_parent_structure=_value(row, "standardized_parent_structure"),
        inchikey=_value(row, "inchikey", "InChIKey"), identifiers=identifiers)
    return standardize_identity(identity) if standardize else identity


def create_repository(directory, backend):
    if backend == "sqlite":
        return SQLiteEvidenceRepository(directory / "evidence.sqlite")
    if backend == "duckdb":
        return DuckDBEvidenceRepository(directory / "evidence.duckdb")
    if backend == "parquet":
        return ParquetEvidenceRepository(directory / "evidence_parquet")
    raise ValueError(f"Unknown evidence backend: {backend}")


class 公开证据聚合插件(基础插件接口):
    插件标识 = "公开证据聚合"

    def 执行(self, 数据上下文):
        context = 数据上下文
        legacy = "公开候选" not in context
        candidates = candidates_for_legacy(context) if legacy else context["公开候选"]
        candidates = candidates.to_dict("records") if isinstance(candidates, pd.DataFrame) else list(candidates)
        manager = context.get("数据管理器")
        directory = Path(context.get("公开证据目录") or (manager.软件数据库目录 / "公开证据" if manager else "数据/软件数据库/公开证据"))
        supplied_cache = context.get("原始响应缓存")
        cache = supplied_cache if supplied_cache is not None else RawResponseCache(directory / "raw.sqlite")
        if legacy and manager is not None and context.get("允许使用缓存", True):
            import_legacy_ghs(manager, cache)
        supplied_repository = context.get("证据存储")
        # 旧 GHS 外观不强制增加依赖；新公开数据流程默认 DuckDB。
        try:
            repository = supplied_repository if supplied_repository is not None else create_repository(directory, context.get("证据存储后端", "sqlite" if legacy else "duckdb"))
        except Exception:
            if supplied_cache is None:
                cache.close()
            raise
        registry = context.get("数据源注册表") or create_registry(cache,
            allow_network=bool(context.get("允许网络公开查询", "公开毒理候选" in context or context.get("启用网络毒性查询", False))),
            use_cache=bool(context.get("允许使用缓存", True)))
        provider_ids = ["pubchem"] if legacy else context.get("公开数据源", ["pubchem"])
        capabilities = ("hazard",) if legacy else tuple(context.get("公开能力", ("properties",)))
        logs, all_evidence, identities, legacy_rows = [], [], [], []
        invalid_ids = set()
        try:
            for row in candidates:
                identity = candidate_identity(row, standardize=False)
                try:
                    identity = standardize_identity(identity)
                except ValueError:
                    invalid_ids.add(identity.compound_id)
                    result = ProviderResult("identity_conflict", message="Observed structure and identity could not be verified; candidate isolated")
                    logs.append({"compound_id": identity.compound_id, "source": "candidate", "capability": "identity",
                                 "status": result.status, "message": result.message})
                    if legacy:
                        legacy_rows.append((row, identity, result))
                    identities.append(identity)
                    continue
                identities.append(identity)
                for provider in registry.providers(provider_ids):
                    supported = [capability for capability in capabilities if capability in provider.capabilities()]
                    for capability in capabilities:
                        if capability not in supported:
                            logs.append({"compound_id": identity.compound_id, "source": provider.provider_id,
                                         "capability": capability, "status": "unsupported", "message": "capability unsupported"})
                    if not supported:
                        continue
                    resolved_identity = identity
                    try:
                        resolution = provider.resolve_identity(identity)
                        if resolution.status != "ok" or resolution.identity is None:
                            logs.append({"compound_id": identity.compound_id, "source": provider.provider_id,
                                         "capability": "identity", "status": resolution.status, "message": resolution.message})
                            if legacy:
                                legacy_rows.append((row, identity, resolution))
                            continue
                        resolved_identity = resolution.identity
                        for capability in supported:
                            method = {"properties": provider.fetch_properties, "hazard": provider.fetch_hazard,
                                      "bioactivity": provider.fetch_bioactivity, "toxicokinetics": provider.fetch_toxicokinetics}.get(capability)
                            result = method(resolved_identity) if method else ProviderResult("unsupported", message="Unsupported fetch operation")
                            repository.add(result.evidence)
                            all_evidence.extend(result.evidence)
                            logs.append({"compound_id": identity.compound_id, "source": provider.provider_id,
                                         "capability": capability, "status": result.status, "message": result.message,
                                         "evidence_count": len(result.evidence), "raw_record_ids": list(result.raw_record_ids)})
                            if legacy:
                                legacy_rows.append((row, resolved_identity, result))
                    except (RuntimeError, ValueError, KeyError) as error:
                        # 第三方异常可能包含请求详情；只输出异常类型。
                        result = ProviderResult("error", message=f"{type(error).__name__}: source query or parsing failed; inspect raw cache")
                        logs.append({"compound_id": identity.compound_id, "source": provider.provider_id,
                                     "capability": "query", "status": "error", "message": result.message})
                        if legacy:
                            legacy_rows.append((row, resolved_identity, result))
            if legacy:
                return save_legacy(context, legacy_rows, cache)
            resolved = []
            for value in context.get("物性请求", []):
                request = value if isinstance(value, EvidenceRequest) else EvidenceRequest(**value)
                if request.compound_id in invalid_ids:
                    resolved.append(ResolvedProperty(request, "identity_conflict", reason="Candidate identity validation failed"))
                    continue
                observed = next((i.observed_structure for i in identities if i.compound_id == request.compound_id), "")
                if observed and request.observed_structure is None:
                    request = replace(request, observed_structure=observed)
                evidence = repository.query(compound_id=request.compound_id, property_id=request.property_id,
                                            sources=request.sources or tuple(provider_ids))
                resolved.append(EvidenceResolver().resolve(request, evidence))
            return {"证据": tuple(all_evidence), "物性采用结果": tuple(resolved), "查询日志": pd.DataFrame(logs),
                    "候选身份": tuple(identities), "证据存储位置": str(directory)}
        finally:
            if supplied_repository is None:
                repository.close()
            if supplied_cache is None:
                cache.close()
