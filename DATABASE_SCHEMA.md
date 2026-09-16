# Database Schema for AI Incident Copilot

## Overview

This schema is designed for Day 1-2 implementation with future extensibility for ML features (embeddings, anomaly detection, clustering).

---

## Tables

### 1. logs

Stores raw and parsed log entries with support for vector embeddings.

```sql
CREATE TABLE logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    service VARCHAR(100),
    level VARCHAR(20) CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    raw_log TEXT NOT NULL,
    template_id INTEGER,
    parameters JSONB,
    embedding VECTOR(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_logs_timestamp ON logs(timestamp DESC);
CREATE INDEX idx_logs_service ON logs(service);
CREATE INDEX idx_logs_level ON logs(level);
CREATE INDEX idx_logs_created_at ON logs(created_at DESC);

-- Composite index for common queries
CREATE INDEX idx_logs_service_level_timestamp ON logs(service, level, timestamp DESC);

-- Vector index (add later when you have data)
-- CREATE INDEX ON logs USING hnsw (embedding vector_cosine_ops);
```

**Column Descriptions:**
- `id`: Unique identifier (UUID)
- `timestamp`: When the log event occurred (from log itself)
- `service`: Service/component that generated the log (e.g., "api-service", "database")
- `level`: Log severity level
- `message`: Parsed log message (cleaned)
- `raw_log`: Original log line as received
- `template_id`: Links to log_templates table (for Drain3, Day 3+)
- `parameters`: Extracted parameters from template (JSON)
- `embedding`: Vector representation for semantic search (384 dimensions)
- `metadata`: Additional flexible data (JSON)
- `created_at`: When record was inserted into database

---

### 2. incidents

Groups related anomalies and tracks incident lifecycle.

```sql
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'closed')),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    affected_services TEXT[],
    root_cause TEXT,
    resolution TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_severity ON incidents(severity);
CREATE INDEX idx_incidents_start_time ON incidents(start_time DESC);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);

-- Composite index for dashboard queries
CREATE INDEX idx_incidents_status_severity ON incidents(status, severity);
```

**Column Descriptions:**
- `id`: Unique identifier
- `title`: Short incident title (e.g., "Database Connection Timeout")
- `description`: Detailed description
- `severity`: Impact level
- `status`: Current incident state
- `start_time`: When incident began
- `end_time`: When incident was resolved (NULL if ongoing)
- `affected_services`: Array of impacted services
- `root_cause`: Identified root cause (filled by LLM or human)
- `resolution`: How it was resolved
- `metadata`: Additional data (deployment info, alerts, etc.)
- `created_at`: When incident was created in system
- `updated_at`: Last modification time

---

### 3. log_templates

Stores Drain3 log templates for pattern recognition (Day 3+).

```sql
CREATE TABLE log_templates (
    id SERIAL PRIMARY KEY,
    template TEXT NOT NULL UNIQUE,
    cluster_id INTEGER NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_templates_cluster_id ON log_templates(cluster_id);
CREATE INDEX idx_templates_occurrence ON log_templates(occurrence_count DESC);
```

**Column Descriptions:**
- `id`: Auto-incrementing ID
- `template`: Log template pattern (e.g., "User <*> logged in from <*>")
- `cluster_id`: Drain3 cluster identifier
- `occurrence_count`: How many times this template appeared
- `first_seen`: First occurrence timestamp
- `last_seen`: Most recent occurrence
- `metadata`: Additional template info

---

### 4. scan_runs

Stores one row per repo security scan, tracking status lifecycle (queued → running → completed/failed) and the scored report. Runtime schema (database.py SCHEMA_SQL) uses TEXT ids/timestamps; shown here as implemented.

```sql
CREATE TABLE scan_runs (
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
    created_at TEXT DEFAULT NOW(),
    updated_at TEXT DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_scan_runs_status ON scan_runs(status);
CREATE INDEX idx_scan_runs_created_at ON scan_runs(created_at DESC);
```

**Column Descriptions:**
- `id`: Unique scan identifier (TEXT uuid)
- `repo_url`: Submitted repository URL (allowlisted https host only)
- `name`: Optional user-provided label
- `status`: Scan lifecycle state
- `score`: 0-100 security score (lower = worse)
- `grade`: Letter grade A/B/C/D/F derived from score
- `summary`: One-line human summary of findings
- `error`: Failure message when status is failed
- `total_files`: Number of source files walked
- `metadata`: JSON blob — sub-scores (`secrets_score`, `code_score`, `config_score`) and LLM stats
- `created_at`: When the scan was submitted (TEXT timestamp)
- `updated_at`: Last status change (TEXT timestamp)

---

### 5. scan_findings

Stores individual findings produced by the rules engine and/or LLM deep-review, linked to a scan run.

```sql
CREATE TABLE scan_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('critical','high','medium','low')),
    category TEXT NOT NULL,
    rule_id TEXT,
    file TEXT NOT NULL,
    line INTEGER,
    evidence TEXT,
    description TEXT NOT NULL,
    remediation TEXT,
    promoted_to_incident BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_scan_findings_scan_id ON scan_findings(scan_id);
```

**Column Descriptions:**
- `id`: Unique finding identifier (TEXT — deterministic sha1 of repo_url|rule_id|file|line so rescans dedupe)
- `scan_id`: Owning scan run (→ scan_runs.id)
- `severity`: critical/high/medium/low
- `category`: `secrets` | `code` | `config` (or LLM category string)
- `rule_id`: Matching rule identifier (NULL for LLM-only findings)
- `file`: Relative file path in the scanned repo
- `line`: Line number of the match (NULL if unknown)
- `evidence`: Truncated + masked matching line (≤200 chars)
- `description`: Human-readable description
- `remediation`: Suggested fix
- `promoted_to_incident`: Whether an incident was created (auto or manual)

---

### 6. Relationships

**Current (Day 1-2):**
- `logs.template_id` → `log_templates.id` (foreign key, added Day 3+)
- `scan_findings.scan_id` → `scan_runs.id` (no FK constraint, consistent with existing loose coupling)

### Future (Day 3+)
- `incident_logs` junction table to link incidents with logs
- `anomalies` table to store detected anomalies
- `deployments` table to track deployment events

---

## Sample Data

### Insert Test Log
```sql
INSERT INTO logs (timestamp, service, level, message, raw_log)
VALUES (
    '2026-05-19T10:00:00Z',
    'api-service',
    'ERROR',
    'Database connection timeout after 5s',
    '2026-05-19T10:00:00Z [api-service] ERROR Database connection timeout after 5s'
);
```

### Insert Test Incident
```sql
INSERT INTO incidents (title, severity, start_time, affected_services)
VALUES (
    'Database Connection Timeout',
    'critical',
    '2026-05-19T10:00:00Z',
    ARRAY['api-service', 'database']
);
```

---

## Query Examples

### Get Recent Errors
```sql
SELECT * FROM logs
WHERE level = 'ERROR'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 100;
```

### Get Logs by Service and Time Range
```sql
SELECT * FROM logs
WHERE service = 'api-service'
  AND timestamp BETWEEN '2026-05-19T09:00:00Z' AND '2026-05-19T11:00:00Z'
ORDER BY timestamp DESC;
```

### Get Open Critical Incidents
```sql
SELECT * FROM incidents
WHERE status = 'open'
  AND severity = 'critical'
ORDER BY start_time DESC;
```

### Count Logs by Level
```sql
SELECT level, COUNT(*) as count
FROM logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY level
ORDER BY count DESC;
```

### List Scans With Finding Counts
```sql
SELECT s.*, COUNT(f.id)::int AS finding_count
FROM scan_runs s
LEFT JOIN scan_findings f ON f.scan_id = s.id
GROUP BY s.id
ORDER BY s.created_at DESC
LIMIT 50;
```

### Get Findings For a Scan (by severity)
```sql
SELECT * FROM scan_findings
WHERE scan_id = '<scan-id>'
ORDER BY severity DESC, file ASC;
```

---

## Performance Considerations

### Index Strategy
- **Create indexes AFTER bulk data insertion** for better performance
- Use `CREATE INDEX CONCURRENTLY` in production to avoid blocking writes
- Monitor index usage with `pg_stat_user_indexes`

### Vector Index (Day 7+)
```sql
-- Only create after you have embeddings
-- HNSW is faster than IVFFlat for most use cases
CREATE INDEX ON logs USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters:**
- `m = 16`: Number of connections per layer (higher = better recall, more memory)
- `ef_construction = 64`: Size of dynamic candidate list (higher = better quality, slower build)

### Partitioning (Future)
For high-volume logs (>10M rows), consider partitioning by timestamp:
```sql
-- Partition by month
CREATE TABLE logs_2026_05 PARTITION OF logs
FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

---

## Migration Strategy

### Day 1-2: Manual SQL
Run schema directly in Supabase SQL Editor.

### Day 3+: Use Alembic
```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add anomalies table"

# Apply migration
alembic upgrade head
```

---

## Backup & Recovery

### Supabase Automatic Backups
- Free tier: Daily backups, 7-day retention
- Pro tier: Point-in-time recovery

### Manual Backup
```bash
# Export schema
pg_dump -h db.your-project.supabase.co -U postgres -s > schema.sql

# Export data
pg_dump -h db.your-project.supabase.co -U postgres -a > data.sql
```

---

## Security

### Row Level Security (RLS)
Enable RLS for multi-tenant scenarios (future):
```sql
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

-- Example policy: users can only see their organization's logs
CREATE POLICY logs_org_isolation ON logs
FOR SELECT
USING (auth.jwt() ->> 'org_id' = metadata->>'org_id');
```

### API Key Security
- Use Supabase service role key for backend (full access)
- Use anon key for frontend (RLS enforced)
- Never commit keys to git

---

## Monitoring

### Useful Queries

**Table Sizes:**
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Index Usage:**
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

## Next Steps

After Day 1-2:
- Add `anomalies` table for PyOD results
- Add `incident_logs` junction table
- Add `deployments` table for correlation
- Implement vector search with pgvector
- Set up automated backups
