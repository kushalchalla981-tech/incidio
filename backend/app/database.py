import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.config import settings


JSON_COLUMNS = {
    "logs": {"metadata", "parameters", "embedding"},
    "incidents": {"metadata", "affected_services"},
    "log_templates": {"metadata"},
    "scan_runs": {"metadata", "scan_options"},
    "scan_findings": {},
    "security_projects": {"tech_stack"},
}

TIMESTAMP_COLUMNS = {
    "logs": {"timestamp", "created_at"},
    "incidents": {"start_time", "end_time", "created_at", "updated_at"},
    "log_templates": {"first_seen", "last_seen"},
    "scan_runs": {"created_at", "updated_at"},
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    service TEXT,
    level TEXT CHECK (level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    message TEXT NOT NULL,
    raw_log TEXT NOT NULL,
    template_id INTEGER,
    parameters TEXT,
    embedding TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT CHECK (severity IN ('low','medium','high','critical')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open','investigating','resolved','closed')),
    start_time TEXT NOT NULL,
    end_time TEXT,
    affected_services TEXT,
    root_cause TEXT,
    resolution TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT NOW(),
    updated_at TEXT DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_start_time ON incidents(start_time DESC);

CREATE TABLE IF NOT EXISTS log_templates (
    id SERIAL PRIMARY KEY,
    template TEXT NOT NULL UNIQUE,
    cluster_id INTEGER NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    first_seen TEXT DEFAULT NOW(),
    last_seen TEXT DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    name TEXT,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','completed','failed')),
    score REAL,
    grade TEXT CHECK (grade IN ('A','B','C','D','F')),
    summary TEXT,
    error TEXT,
    total_files INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    source_type TEXT NOT NULL DEFAULT 'repo'
        CHECK (source_type IN ('repo','url','zip')),
    project_id TEXT,
    source_ref TEXT,
    scan_options TEXT DEFAULT '{}',
    scan_version TEXT,
    created_at TEXT DEFAULT NOW(),
    updated_at TEXT DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scan_runs_status ON scan_runs(status);
CREATE INDEX IF NOT EXISTS idx_scan_runs_created_at ON scan_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_runs_project_id ON scan_runs(project_id);

CREATE TABLE IF NOT EXISTS scan_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('critical','high','medium','low','informational')),
    category TEXT NOT NULL,
    rule_id TEXT,
    file TEXT NOT NULL,
    line INTEGER,
    evidence TEXT,
    description TEXT NOT NULL,
    remediation TEXT,
    promoted_to_incident BOOLEAN DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','resolved','accepted','false_positive')),
    status_note TEXT,
    confidence TEXT DEFAULT 'potential'
        CHECK (confidence IN ('confirmed','strong','potential','informational')),
    cwe TEXT,
    owasp TEXT,
    title TEXT,
    impact TEXT,
    attack_scenario TEXT,
    verification TEXT,
    suggested_fix TEXT,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_scan_findings_scan_id ON scan_findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_findings_status ON scan_findings(status);

CREATE TABLE IF NOT EXISTS security_projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('repo','url','zip')),
    source_ref TEXT NOT NULL,
    tech_stack TEXT DEFAULT '{}',
    last_scan_id TEXT,
    created_at TEXT DEFAULT NOW(),
    updated_at TEXT DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_security_projects_source ON security_projects(source_type, source_ref);
"""

MIGRATIONS_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_runs' AND column_name = 'source_type'
    ) THEN
        ALTER TABLE scan_runs ADD COLUMN source_type TEXT NOT NULL DEFAULT 'repo';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_runs' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE scan_runs ADD COLUMN project_id TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_runs' AND column_name = 'source_ref'
    ) THEN
        ALTER TABLE scan_runs ADD COLUMN source_ref TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_runs' AND column_name = 'scan_options'
    ) THEN
        ALTER TABLE scan_runs ADD COLUMN scan_options TEXT DEFAULT '{}';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_runs' AND column_name = 'scan_version'
    ) THEN
        ALTER TABLE scan_runs ADD COLUMN scan_version TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'status'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN status TEXT NOT NULL DEFAULT 'open';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'status_note'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN status_note TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'confidence'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN confidence TEXT DEFAULT 'potential';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'cwe'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN cwe TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'owasp'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN owasp TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'title'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN title TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'impact'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN impact TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'attack_scenario'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN attack_scenario TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'verification'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN verification TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'suggested_fix'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN suggested_fix TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_findings' AND column_name = 'source'
    ) THEN
        ALTER TABLE scan_findings ADD COLUMN source TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'scan_findings_severity_check'
    ) THEN
        ALTER TABLE scan_findings DROP CONSTRAINT scan_findings_severity_check;
        ALTER TABLE scan_findings ADD CONSTRAINT scan_findings_severity_check
            CHECK (severity IN ('critical','high','medium','low','informational'));
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'scan_runs_source_type_check'
    ) THEN
        ALTER TABLE scan_runs DROP CONSTRAINT scan_runs_source_type_check;
    END IF;
END $$;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'scan_runs_source_type_check'
    ) THEN
        ALTER TABLE scan_runs ADD CONSTRAINT scan_runs_source_type_check
            CHECK (source_type IN ('repo','url','zip'));
    END IF;
END $$;
"""


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            await conn.execute(MIGRATIONS_SQL)

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    @staticmethod
    def _serialize(data: dict, table: str) -> dict:
        d = dict(data)
        for col in JSON_COLUMNS.get(table, set()):
            if col in d and d[col] is not None:
                d[col] = json.dumps(d[col])
        return d

    @staticmethod
    def _deserialize(d: dict, table: str) -> dict:
        result = dict(d)
        for col in JSON_COLUMNS.get(table, set()):
            if col in result and isinstance(result[col], str):
                try:
                    result[col] = json.loads(result[col])
                except (json.JSONDecodeError, TypeError):
                    pass
        for col in TIMESTAMP_COLUMNS.get(table, set()):
            if col in result and isinstance(result[col], str):
                try:
                    result[col] = datetime.fromisoformat(result[col])
                except (ValueError, TypeError):
                    pass
        return result

    async def check_health(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    @staticmethod
    def _placeholders(count: int, start: int = 1) -> str:
        return ", ".join(f"${i}" for i in range(start, start + count))

    async def insert(self, table: str, data: dict) -> dict:
        record = dict(data)
        if "id" not in record:
            record["id"] = str(uuid.uuid4())
        record = self._serialize(record, table)
        columns = list(record.keys())
        values = list(record.values())
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({self._placeholders(len(columns))}) RETURNING *"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *values)
        return self._deserialize(dict(row), table)

    async def insert_batch(self, table: str, records: list[dict]) -> int:
        if not records:
            return 0
        serialized = []
        for record in records:
            r = dict(record)
            if "id" not in r:
                r["id"] = str(uuid.uuid4())
            serialized.append(self._serialize(r, table))

        first = serialized[0]
        columns = list(first.keys())
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({self._placeholders(len(columns))})"
        values_list = [list(r.values()) for r in serialized]
        async with self.pool.acquire() as conn:
            await conn.executemany(sql, values_list)
        return len(serialized)

    async def get_by_id(self, table: str, id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", id)
        if row is None:
            return None
        return self._deserialize(dict(row), table)

    async def update_by_id(self, table: str, id: str, data: dict) -> Optional[dict]:
        record = self._serialize(data, table)
        set_clause = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(record))
        values = list(record.values()) + [id]
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ${len(record) + 1} RETURNING *"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *values)
        if row is None:
            return None
        return self._deserialize(dict(row), table)

    async def upsert_template(self, cluster_id: int, template: str):
        sql = """
            INSERT INTO log_templates (template, cluster_id, occurrence_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (cluster_id) DO UPDATE SET
                occurrence_count = log_templates.occurrence_count + 1,
                last_seen = NOW(),
                template = EXCLUDED.template
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, template, cluster_id)

    async def query_logs(
        self,
        service: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params = []
        idx = 1
        if service:
            conditions.append(f"service = ${idx}")
            params.append(service)
            idx += 1
        if level:
            conditions.append(f"level = ${idx}")
            params.append(level.upper())
            idx += 1
        if start_time:
            conditions.append(f"timestamp >= ${idx}")
            params.append(start_time)
            idx += 1
        if end_time:
            conditions.append(f"timestamp <= ${idx}")
            params.append(end_time)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM logs {where} ORDER BY timestamp DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [self._deserialize(dict(r), "logs") for r in rows]

    async def query_logs_range(
        self,
        service: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[dict]:
        conditions = []
        params = []
        idx = 1
        if service:
            conditions.append(f"service = ${idx}")
            params.append(service)
            idx += 1
        if start_time:
            conditions.append(f"timestamp >= ${idx}")
            params.append(start_time)
            idx += 1
        if end_time:
            conditions.append(f"timestamp <= ${idx}")
            params.append(end_time)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM logs {where} ORDER BY timestamp ASC"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [self._deserialize(dict(r), "logs") for r in rows]

    async def update_embedding(self, log_id: str, embedding: list[float]):
        serialized = json.dumps(embedding)
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE logs SET embedding = $1 WHERE id = $2", serialized, log_id)

    async def get_logs_without_embeddings(self, limit: int = 500) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, message, raw_log, timestamp, service, level "
                "FROM logs WHERE embedding IS NULL OR embedding = '[]' "
                "ORDER BY timestamp DESC LIMIT $1",
                limit,
            )
        return [dict(r) for r in rows]

    async def get_all_embeddings(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, embedding, message, raw_log, timestamp, service, level "
                "FROM logs WHERE embedding IS NOT NULL AND embedding != '[]'"
            )
        return [dict(r) for r in rows]

    async def query_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params = []
        idx = 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if severity:
            conditions.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM incidents {where} ORDER BY start_time DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [self._deserialize(dict(r), "incidents") for r in rows]

    async def insert_scan_run(self, repo_url: str, name: Optional[str] = None) -> dict:
        return await self.insert("scan_runs", {"repo_url": repo_url, "name": name, "status": "queued"})

    async def update_scan_status(self, scan_id: str, status: str, *, score=None, grade=None,
                                 summary=None, error=None, total_files=None, metadata=None) -> None:
        data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if score is not None: data["score"] = score
        if grade is not None: data["grade"] = grade
        if summary is not None: data["summary"] = summary
        if error is not None: data["error"] = error
        if total_files is not None: data["total_files"] = total_files
        if metadata is not None: data["metadata"] = metadata
        await self.update_by_id("scan_runs", scan_id, data)

    async def get_scan_runs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        sql = ("SELECT s.*, COUNT(f.id)::int AS finding_count FROM scan_runs s "
               "LEFT JOIN scan_findings f ON f.scan_id = s.id "
               "GROUP BY s.id ORDER BY s.created_at DESC LIMIT $1 OFFSET $2")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, limit, offset)
        return [self._deserialize(dict(r), "scan_runs") for r in rows]

    async def get_scan_run(self, scan_id: str) -> Optional[dict]:
        return await self.get_by_id("scan_runs", scan_id)

    async def get_scan_findings(self, scan_id: str) -> list[dict]:
        sql = "SELECT * FROM scan_findings WHERE scan_id = $1 ORDER BY severity DESC, file ASC"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, scan_id)
        return [self._deserialize(dict(r), "scan_findings") for r in rows]

    async def mark_finding_promoted(self, finding_id: str) -> None:
        await self.pool.execute("UPDATE scan_findings SET promoted_to_incident = TRUE WHERE id = $1", finding_id)

    async def finding_has_incident(self, finding_id: str) -> bool:
        row = await self.pool.fetchval(
            "SELECT id FROM incidents WHERE metadata::jsonb @> $1::jsonb LIMIT 1",
            json.dumps({"finding_id": finding_id}))
        return row is not None

    async def active_scan_for_repo(self, repo_url: str) -> Optional[dict]:
        row = await self.pool.fetchrow(
            "SELECT * FROM scan_runs WHERE repo_url = $1 AND status IN ('queued','running') LIMIT 1",
            repo_url)
        return self._deserialize(dict(row), "scan_runs") if row else None

    async def active_scan_for_project(self, project_id: str) -> Optional[dict]:
        row = await self.pool.fetchrow(
            "SELECT * FROM scan_runs WHERE project_id = $1 AND status IN ('queued','running') LIMIT 1",
            project_id)
        return self._deserialize(dict(row), "scan_runs") if row else None

    async def get_distinct_services(self) -> list[str]:
        rows = await self.pool.fetch(
            "SELECT DISTINCT service FROM logs WHERE service IS NOT NULL AND service != '' ORDER BY service")
        return [r["service"] for r in rows]

    async def insert_project(self, name: Optional[str], source_type: str, source_ref: str) -> dict:
        return await self.insert("security_projects", {
            "name": name,
            "source_type": source_type,
            "source_ref": source_ref,
        })

    async def get_project(self, project_id: str) -> Optional[dict]:
        return await self.get_by_id("security_projects", project_id)

    async def find_project(self, source_type: str, source_ref: str) -> Optional[dict]:
        row = await self.pool.fetchrow(
            "SELECT * FROM security_projects WHERE source_type = $1 AND source_ref = $2 ORDER BY created_at LIMIT 1",
            source_type, source_ref)
        return self._deserialize(dict(row), "security_projects") if row else None

    async def get_projects(self, limit: int = 50, offset: int = 0) -> list[dict]:
        sql = ("SELECT p.*, s.status AS last_scan_status, s.score AS last_scan_score, "
               "s.grade AS last_scan_grade, s.summary AS last_scan_summary, "
               "s.created_at AS last_scan_created_at "
               "FROM security_projects p LEFT JOIN scan_runs s ON s.id = p.last_scan_id "
               "ORDER BY p.updated_at DESC LIMIT $1 OFFSET $2")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, limit, offset)
        return [self._deserialize(dict(r), "security_projects") for r in rows]

    async def update_project_last_scan(self, project_id: str, scan_id: str) -> None:
        await self.pool.execute(
            "UPDATE security_projects SET last_scan_id = $1, updated_at = NOW() WHERE id = $2",
            scan_id, project_id)

    async def get_scan_runs_for_project(self, project_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        sql = ("SELECT s.*, COUNT(f.id)::int AS finding_count FROM scan_runs s "
               "LEFT JOIN scan_findings f ON f.scan_id = s.id "
               "WHERE s.project_id = $1 "
               "GROUP BY s.id ORDER BY s.created_at DESC LIMIT $2 OFFSET $3")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, project_id, limit, offset)
        return [self._deserialize(dict(r), "scan_runs") for r in rows]

    async def update_finding_status(self, finding_id: str, status: str, note: Optional[str] = None) -> Optional[dict]:
        data = {"status": status, "status_note": note}
        return await self.update_by_id("scan_findings", finding_id, data)

    async def query_findings(
        self,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params = []
        idx = 1
        if severity:
            conditions.append(f"f.severity = ${idx}")
            params.append(severity)
            idx += 1
        if category:
            conditions.append(f"f.category = ${idx}")
            params.append(category)
            idx += 1
        if status:
            conditions.append(f"f.status = ${idx}")
            params.append(status)
            idx += 1
        if project_id:
            conditions.append(f"s.project_id = ${idx}")
            params.append(project_id)
            idx += 1
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = (f"SELECT f.*, s.project_id AS scan_project_id, s.source_type AS scan_source_type, "
               f"s.repo_url AS scan_repo_url, s.created_at AS scan_created_at "
               f"FROM scan_findings f JOIN scan_runs s ON s.id = f.scan_id "
               f"{where} ORDER BY f.severity DESC, f.file ASC LIMIT ${idx} OFFSET ${idx + 1}")
        params.extend([limit, offset])
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [self._deserialize(dict(r), "scan_findings") for r in rows]


_db: Optional[Database] = None


async def get_db() -> Database:
    global _db
    if _db is None or _db.pool is None:
        if _db is None:
            _db = Database(settings.DATABASE_URL)
        await _db.connect()
    return _db


async def check_db_health() -> bool:
    db = await get_db()
    return await db.check_health()
