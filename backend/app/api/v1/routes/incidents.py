from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.models import IncidentCreate, IncidentResponse, IncidentUpdate

router = APIRouter()


@router.post("/incidents", response_model=IncidentResponse, status_code=201)
async def create_incident(incident: IncidentCreate):
    try:
        db = await get_db()
        return await db.insert("incidents", incident.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    return await db.query_incidents(
        status=status, severity=severity, limit=limit, offset=offset
    )


@router.get("/incidents/services")
async def list_services():
    db = await get_db()
    return await db.get_distinct_services()


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str):
    db = await get_db()
    result = await db.get_by_id("incidents", incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(incident_id: str, update: IncidentUpdate):
    try:
        db = await get_db()
        data = {k: v for k, v in update.model_dump(mode="json").items() if v is not None}
        existing = await db.get_by_id("incidents", incident_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Incident not found")

        metadata = dict(existing.get("metadata") or {})
        timeline = list(metadata.get("timeline") or [])
        now = datetime.now(timezone.utc).isoformat()
        if "status" in data and data["status"] != existing.get("status"):
            timeline.append({
                "action": "status_changed",
                "from": existing.get("status"),
                "to": data["status"],
                "timestamp": now,
            })
            metadata["timeline"] = timeline
            data["metadata"] = metadata

        data["updated_at"] = now
        result = await db.update_by_id("incidents", incident_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="Incident not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
