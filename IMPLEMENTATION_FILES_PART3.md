# Implementation Files - Part 3: Incidents Route, Docker

## backend/app/api/v1/routes/incidents.py

```python
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.database import get_supabase_client
from app.models import IncidentCreate, IncidentUpdate, IncidentResponse

router = APIRouter()


@router.post("/incidents", response_model=IncidentResponse, status_code=201)
async def create_incident(incident: IncidentCreate):
    try:
        data = incident.model_dump(mode="json")
        result = get_supabase_client().table("incidents").insert(data).execute()
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    q = get_supabase_client().table("incidents").select("*")
    if status:
        q = q.eq("status", status)
    if severity:
        q = q.eq("severity", severity)
    result = q.order("start_time", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str):
    result = (
        get_supabase_client()
        .table("incidents")
        .select("*")
        .eq("id", incident_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result.data[0]


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(incident_id: str, update: IncidentUpdate):
    data = {k: v for k, v in update.model_dump(mode="json").items() if v is not None}
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = (
        get_supabase_client()
        .table("incidents")
        .update(data)
        .eq("id", incident_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result.data[0]
```

---

## backend/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml (root directory)

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend/app:/app/app   # hot reload in dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## .gitignore (root directory)

```
# Python
__pycache__/
*.py[cod]
venv/
env/
.venv/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Docker
*.log
```

---

## Supabase Schema SQL

Run this in the Supabase SQL Editor (Database → SQL Editor → New Query):

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Logs table
CREATE TABLE IF NOT EXISTS logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    service VARCHAR(100),
    level VARCHAR(20) CHECK (level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    message TEXT NOT NULL,
    raw_log TEXT NOT NULL,
    template_id INTEGER,
    parameters JSONB,
    embedding VECTOR(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Incidents table
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(20) CHECK (severity IN ('low','medium','high','critical')),
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open','investigating','resolved','closed')),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    affected_services TEXT[],
    root_cause TEXT,
    resolution TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Log templates table (used by Drain3 on Day 3+)
CREATE TABLE IF NOT EXISTS log_templates (
    id SERIAL PRIMARY KEY,
    template TEXT NOT NULL UNIQUE,
    cluster_id INTEGER NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_start_time ON incidents(start_time DESC);
```
