import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.database import get_db
from app.models import LogBatchCreate, LogCreate, LogResponse, LogUploadResponse
from app.services.embeddings import batch_get_embeddings
from app.services.parser import extract_params, parse_log

router = APIRouter()

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+)\s+\[(?P<service>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<message>.+)$"
)
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@router.post("/logs", response_model=LogResponse, status_code=201)
async def create_log(log: LogCreate):
    try:
        db = await get_db()
        return await db.insert("logs", log.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/batch", status_code=201)
async def create_logs_batch(payload: LogBatchCreate):
    if not payload.logs:
        raise HTTPException(status_code=400, detail="No logs provided")
    try:
        db = await get_db()
        data = [l.model_dump(mode="json") for l in payload.logs]
        inserted = await db.insert_batch("logs", data)
        return {"inserted": inserted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/upload", response_model=LogUploadResponse)
async def upload_log_file(file: UploadFile = File(...)):
    content = await file.read()
    lines = content.decode("utf-8", errors="replace").splitlines()

    db = await get_db()
    batch, errors, seen_clusters = [], [], set()
    inserted = 0

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
            raw_log = line
            drain_result = parse_log(raw_log)
            params = extract_params(raw_log, drain_result["template"])
            cluster_id = drain_result["cluster_id"]

            if cluster_id not in seen_clusters:
                await db.upsert_template(cluster_id, drain_result["template"])
                seen_clusters.add(cluster_id)

            batch.append({
                "timestamp": datetime.fromisoformat(
                    m.group("timestamp").replace("Z", "+00:00")
                ).isoformat(),
                "service": m.group("service"),
                "level": level,
                "message": m.group("message"),
                "raw_log": raw_log,
                "template_id": cluster_id,
                "parameters": params,
                "metadata": {},
            })
        except Exception as e:
            errors.append(str(e))

    if batch:
        try:
            raw_texts = [b["raw_log"] for b in batch]
            embeddings = batch_get_embeddings(raw_texts)
            for i, emb in enumerate(embeddings):
                batch[i]["embedding"] = emb
        except Exception:
            for b in batch:
                b["embedding"] = []

        inserted = await db.insert_batch("logs", batch)

    return LogUploadResponse(
        logs_processed=inserted,
        logs_failed=len(errors),
        errors=errors[:20],
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
    db = await get_db()
    return await db.query_logs(
        service=service,
        level=level,
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/{log_id}", response_model=LogResponse)
async def get_log(log_id: str):
    db = await get_db()
    result = await db.get_by_id("logs", log_id)
    if not result:
        raise HTTPException(status_code=404, detail="Log not found")
    return result
