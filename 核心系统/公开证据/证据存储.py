"""长表存储，索引列用于条件查询，其余信息以 JSON 无损保存。"""

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .数据结构 import PropertyEvidence
from .证据存储接口 import EvidenceRepository


class SQLiteEvidenceRepository(EvidenceRepository):
    def __init__(self, path=":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self._initialize()

    def _initialize(self):
        self.connection.execute("""CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY, compound_id TEXT, property_id TEXT,
            source TEXT, temperature DOUBLE, payload TEXT NOT NULL)""")
        self.connection.execute("CREATE INDEX IF NOT EXISTS evidence_lookup ON evidence(compound_id, property_id, source, temperature)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS evidence_property ON evidence(property_id, source, temperature)")
        self.connection.commit()

    def add(self, evidence):
        rows = [(e.evidence_id, e.compound_id, e.property_id, e.source, e.temperature,
                 json.dumps(asdict(e), ensure_ascii=False, allow_nan=False)) for e in evidence]
        if not rows:
            return
        try:
            self._begin()
            self.connection.executemany("INSERT INTO evidence VALUES (?,?,?,?,?,?) ON CONFLICT (evidence_id) DO NOTHING", rows)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _begin(self):
        pass  # SQLite 在第一次写入时自动开启事务。

    def query(self, *, compound_id=None, property_id=None, sources=(), temperature_range=None):
        clauses, params = [], []
        for key, value in (("compound_id", compound_id), ("property_id", property_id)):
            if value is not None:
                clauses.append(f"{key} = ?")
                params.append(value)
        if sources:
            clauses.append("source IN (" + ",".join("?" for _ in sources) + ")")
            params.extend(sources)
        if temperature_range is not None:
            clauses.append("temperature BETWEEN ? AND ?")
            params.extend(temperature_range)
        sql = "SELECT payload FROM evidence" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY evidence_id"
        return [PropertyEvidence(**json.loads(row[0])) for row in self.connection.execute(sql, params).fetchall()]

    def close(self):
        self.connection.close()


class DuckDBEvidenceRepository(SQLiteEvidenceRepository):
    def __init__(self, path=":memory:"):
        import duckdb
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(path))
        self._initialize()

    def _begin(self):
        self.connection.execute("BEGIN TRANSACTION")

    def export_parquet(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection.execute("COPY evidence TO ? (FORMAT PARQUET)", [str(path)])


class ParquetEvidenceRepository(EvidenceRepository):
    """追加不可变分片；查询通过 Arrow predicate pushdown，重复证据按 ID 去重。"""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def add(self, evidence):
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows = [{"evidence_id": e.evidence_id, "compound_id": e.compound_id,
                 "property_id": e.property_id, "source": e.source, "temperature": e.temperature,
                 "payload": json.dumps(asdict(e), ensure_ascii=False, allow_nan=False)} for e in evidence]
        if rows:
            schema = pa.schema([(name, pa.string()) for name in ("evidence_id", "compound_id", "property_id", "source")]
                               + [("temperature", pa.float64()), ("payload", pa.string())])
            target = self.directory / f"{uuid4().hex}.parquet"
            temporary = target.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), temporary)
            temporary.replace(target)

    def query(self, *, compound_id=None, property_id=None, sources=(), temperature_range=None):
        import pyarrow.dataset as ds
        if not any(self.directory.glob("*.parquet")):
            return []
        filters = []
        for key, value in (("compound_id", compound_id), ("property_id", property_id)):
            if value is not None:
                filters.append(ds.field(key) == value)
        if sources:
            filters.append(ds.field("source").isin(sources))
        if temperature_range is not None:
            filters.extend([ds.field("temperature") >= temperature_range[0], ds.field("temperature") <= temperature_range[1]])
        expression = None
        for f in filters:
            expression = f if expression is None else expression & f
        dataset = ds.dataset([str(p) for p in self.directory.glob("*.parquet")], format="parquet")
        rows = dataset.to_table(columns=["evidence_id", "payload"], filter=expression).to_pylist()
        unique = {row["evidence_id"]: PropertyEvidence(**json.loads(row["payload"])) for row in rows}
        return [unique[key] for key in sorted(unique)]

    def close(self):
        pass
