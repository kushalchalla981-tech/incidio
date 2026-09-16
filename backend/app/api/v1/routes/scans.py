from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.database import get_db
from app.models import IncidentResponse, ScanCreate, ScanResponse
from app.services.scanner import (
    promote_finding_to_incident,
    run_scan,
    validate_repo_url,
)

router = APIRouter()


@router.post("/scans", response_model=ScanResponse, status_code=201)
async def create_scan(scan: ScanCreate, background_tasks: BackgroundTasks):
    try:
        validate_repo_url(scan.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db = await get_db()
    if await db.active_scan_for_repo(scan.repo_url):
        raise HTTPException(status_code=409, detail="A scan for this repo is already queued or running")
    try:
        run = await db.insert_scan_run(scan.repo_url, scan.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    background_tasks.add_task(run_scan, run["id"], scan.repo_url)
    return run


@router.get("/scans", response_model=list[ScanResponse])
async def list_scans(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    return await db.get_scan_runs(limit=limit, offset=offset)


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str):
    db = await get_db()
    run = await db.get_scan_run(scan_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scan not found")
    run["findings"] = await db.get_scan_findings(scan_id)
    run["finding_count"] = len(run["findings"])
    return run


@router.post(
    "/scans/{scan_id}/findings/{finding_id}/incident",
    response_model=IncidentResponse,
    status_code=201,
)
async def promote_finding(scan_id: str, finding_id: str):
    db = await get_db()
    scan = await db.get_scan_run(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    finding = await db.get_by_id("scan_findings", finding_id)
    if not finding or finding.get("scan_id") != scan_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    try:
        incident = await promote_finding_to_incident(db, scan, finding)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not incident:
        raise HTTPException(status_code=409, detail="Finding already promoted to an incident")
    return incident