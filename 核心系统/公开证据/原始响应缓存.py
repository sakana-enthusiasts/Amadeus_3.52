"""原始响应先落盘再解析；缓存键不含解析器版本，旧响应可以离线重解析。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


@dataclass(frozen=True)
class RawRecord:
    raw_record_id: str
    source: str
    endpoint: str
    source_record_id: str
    retrieved_at: str
    status_code: int
    response_hash: str
    parser_version: str
    body: str
    cache_hit: bool = False

    def json(self):
        return json.loads(self.body)


class RawResponseCache:
    def __init__(self, path=":memory:", max_age_seconds=7 * 24 * 3600):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.max_age_seconds = max_age_seconds
        self.connection.execute("""CREATE TABLE IF NOT EXISTS raw_response (
            raw_record_id TEXT PRIMARY KEY, source TEXT, endpoint TEXT, source_record_id TEXT,
            retrieved_at TEXT, status_code INTEGER, response_hash TEXT, parser_version TEXT, body TEXT)""")
        self.connection.execute("CREATE INDEX IF NOT EXISTS raw_lookup ON raw_response(source, endpoint, retrieved_at)")
        self.connection.commit()

    def save(self, source, endpoint, source_record_id, status_code, body, parser_version, *, retrieved_at=None):
        timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            timestamp = parsed.replace(tzinfo=timezone.utc).isoformat()
        response_hash = sha256(body.encode()).hexdigest()
        raw_id = sha256(f"{source}|{endpoint}|{timestamp}|{response_hash}|{status_code}|{uuid4().hex}".encode()).hexdigest()
        record = RawRecord(raw_id, source, endpoint, source_record_id, timestamp, status_code,
                           response_hash, parser_version, body)
        self.connection.execute("INSERT INTO raw_response VALUES (?,?,?,?,?,?,?,?,?)",
                                tuple(getattr(record, key) for key in RawRecord.__dataclass_fields__ if key != "cache_hit"))
        self.connection.commit()
        return record

    def get(self, source, endpoint, *, ignore_age=False):
        row = self.connection.execute("""SELECT * FROM raw_response WHERE source=? AND endpoint=?
            AND status_code IN (200,404) ORDER BY retrieved_at DESC, rowid DESC LIMIT 1""", (source, endpoint)).fetchone()
        if not row:
            return None
        record = RawRecord(*row, cache_hit=True)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(record.retrieved_at)).total_seconds()
        return record if ignore_age or self.max_age_seconds is None or age <= self.max_age_seconds else None

    def records(self, source=None):
        rows = self.connection.execute("SELECT * FROM raw_response" + (" WHERE source=?" if source else ""),
                                      (source,) if source else ()).fetchall()
        return [RawRecord(*row) for row in rows]

    def by_id(self, raw_record_id):
        row = self.connection.execute("SELECT * FROM raw_response WHERE raw_record_id=?", (raw_record_id,)).fetchone()
        return RawRecord(*row) if row else None

    def close(self):
        self.connection.close()
