# Implementation Files - Part 2: main.py, Health Route, Logs Route

## backend/app/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import get_supabase_client
from app.api.v1.routes import health, logs, incidents


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize Supabase client
    get_supabase_client()
    yield
    # Shutdown: nothing to clean up for Supabase


app = FastAPI(
    title="AI Incident Copilot",
    description="Intelligent incident management for small software teams",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(logs.router, prefix=settings.API_V1_PREFIX, tags=["logs"])
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX, tags=["incidents"])
```

---

## backend/app/api/v1/routes/health.py

```python
from fastapi import APIRouter
from datetime import datetime, timezone
from app.database import check_db_health
from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_ok = await check_db_health()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        timestamp=datetime.now(timezone.utc),
    )
```

---

## backend/app/api/v1/routes/logs.py

```python
import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from app.database import get_supabase_client
from app.models import LogCreate, LogResponse, LogBatchCreate, LogUploadResponse

router = APIRouter()

# Regex to parse the sample log format:
# 2026-05-18T10:15:23Z [api-service] INFO User 12345 logged in
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+)\s+\[(?P<service>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<message>.+)$"
)
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _insert_log(data: dict) -> dict:
    result = get_supabase_client().table("logs").insert(data).execute()
    return result.data[0]


@router.post("/logs", response_model=LogResponse, status_code=201)
async def create_log(log: LogCreate):
    try:
        return _insert_log(log.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/batch", status_code=201)
async def create_logs_batch(payload: LogBatchCreate):
    if not payload.logs:
        raise HTTPException(status_code=400, detail="No logs provided")
    try:
        data = [l.model_dump(mode="json") for l in payload.logs]
        result = get_supabase_client().table("logs").insert(data).execute()
        return {"inserted": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/upload", response_model=LogUploadResponse)
async def upload_log_file(file: UploadFile = File(...)):
    content = await file.read()
    lines = content.decode("utf-8", errors="replace").splitlines()

    batch, errors = [], []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = LOG_PATTERN.match(line)
        if not m:
            errors.append(f"Could not parse: {line[:80]}")
            continue
        level = m.group("level").upper()
        if level not in VALID_LEVELS:
            level = "INFO"
        try:
            batch.append({
                "timestamp": datetime.fromisoformat(
                    m.group("timestamp").replace("Z", "+00:00")
                ).isoformat(),
                "service": m.group("service"),
                "level": level,
                "message": m.group("message"),
                "raw_log": line,
                "metadata": {},
            })
        except Exception as e:
            errors.append(str(e))

    inserted = 0
    if batch:
        # Insert in chunks of 500 to stay within Supabase limits
        for i in range(0, len(batch), 500):
            chunk = batch[i:i + 500]
            get_supabase_client().table("logs").insert(chunk).execute()
            inserted += len(chunk)

    return LogUploadResponse(
        logs_processed=inserted,
        logs_failed=len(errors),
        errors=errors[:20],  # cap error list
    )


@router.get("/logs", response_model=list[LogResponse])
async def list_logs(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    q = get_supabase_client().table("logs").select("*")
    if service:
        q = q.eq("service", service)
    if level:
        q = q.eq("level", level.upper())
    if start_time:
        q = q.gte("timestamp", start_time.isoformat())
    if end_time:
        q = q.lte("timestamp", end_time.isoformat())
    result = q.order("timestamp", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/logs/{log_id}", response_model=LogResponse)
async def get_log(log_id: str):
    result = get_supabase_client().table("logs").select("*").eq("id", log_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Log not found")
    return result.data[0]
```
