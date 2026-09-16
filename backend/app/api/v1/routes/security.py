import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile

from app.config import settings
from app.database import get_db
from app.models import (
    CompareItem,
    FindingStatusUpdate,
    ScanComparison,
    ScanResponse,
    SecurityProject,
    SecurityProjectDetail,
    SecurityScanCreate,
    ScanRun,
)
from app.services.scanner import run_security_scan, _finding_id
from app.services.zip_ingest import ZipError, validate_zip_bytes

router = APIRouter()

SCAN_TMP = settings.SCAN_TMP_DIR


@router.post("/security/scans", response_model=ScanRun, status_code=201)
async def create_security_scan(
    payload: SecurityScanCreate,
    background_tasks: BackgroundTasks,
):
    if payload.source_type == "zip":
        raise HTTPException(status_code=422, detail="zip uploads must use POST /security/scans/zip")
    try:
        from app.services.url_checker import validate_live_url
        from app.services.scanner import validate_repo_url
        if payload.source_type == "repo":
            validate_repo_url(payload.source_ref)
        elif payload.source_type == "url":
            validate_live_url(payload.source_ref)
        else:
            raise ValueError(f"unsupported source type: {payload.source_type}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db = await get_db()
    if await db.active_scan_for_repo(payload.source_ref):
        raise HTTPException(status_code=409, detail="A scan for this source is already queued or running")

    project = await db.find_project(payload.source_type, payload.source_ref)
    if project is None:
        project = await db.insert_project(payload.name, payload.source_type, payload.source_ref)
    elif payload.name and not project.get("name"):
        await db.update_by_id("security_projects", project["id"], {"name": payload.name})

    try:
        run = await db.insert("scan_runs", {
            "repo_url": payload.source_ref,
            "name": payload.name,
            "status": "queued",
            "source_type": payload.source_type,
            "project_id": project["id"],
            "source_ref": payload.source_ref,
            "scan_options": payload.options or {},
            "scan_version": settings.SECURITY_SCAN_VERSION,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks.add_task(run_security_scan, run["id"], payload.source_type, payload.source_ref, payload.options or {})
    return run


@router.post("/security/scans/zip", response_model=ScanRun, status_code=201)
async def create_security_scan_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None, max_length=255),
):
    data = await file.read()
    try:
        validate_zip_bytes(data)
    except ZipError as e:
        raise HTTPException(status_code=400, detail=str(e))

    source_ref = file.filename or "upload.zip"
    db = await get_db()
    if await db.active_scan_for_repo(source_ref):
        raise HTTPException(status_code=409, detail="A scan for this source is already queued or running")

    project = await db.find_project("zip", source_ref)
    if project is None:
        project = await db.insert_project(name or source_ref, "zip", source_ref)

    try:
        run = await db.insert("scan_runs", {
            "repo_url": source_ref,
            "name": name,
            "status": "queued",
            "source_type": "zip",
            "project_id": project["id"],
            "source_ref": source_ref,
            "scan_options": {},
            "scan_version": settings.SECURITY_SCAN_VERSION,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    os.makedirs(SCAN_TMP, exist_ok=True)
    zip_path = os.path.join(SCAN_TMP, f"{run['id']}.zip")
    with open(zip_path, "wb") as f:
        f.write(data)

    background_tasks.add_task(run_security_scan, run["id"], "zip", source_ref, {})
    return run


@router.get("/security/projects", response_model=list[SecurityProject])
async def list_projects(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    return await db.get_projects(limit=limit, offset=offset)


@router.get("/security/projects/{project_id}", response_model=SecurityProjectDetail)
async def get_project(project_id: str):
    db = await get_db()
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["scans"] = await db.get_scan_runs_for_project(project_id)
    return project


@router.get("/security/scans", response_model=list[ScanRun])
async def list_security_scans(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    if project_id:
        return await db.get_scan_runs_for_project(project_id, limit=limit, offset=offset)
    return await db.get_scan_runs(limit=limit, offset=offset)


@router.get("/security/scans/{scan_id}", response_model=ScanResponse)
async def get_security_scan(scan_id: str):
    db = await get_db()
    run = await db.get_scan_run(scan_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scan not found")
    run["findings"] = await db.get_scan_findings(scan_id)
    run["finding_count"] = len(run["findings"])
    files = (run.get("metadata") or {}).get("scanned_files") or []
    run["scanned_files"] = files if isinstance(files, list) else []
    return run


@router.get("/security/findings")
async def list_findings(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    return await db.query_findings(
        severity=severity,
        category=category,
        status=status,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )


@router.patch("/security/findings/{finding_id}")
async def update_finding(finding_id: str, update: FindingStatusUpdate):
    db = await get_db()
    result = await db.update_finding_status(finding_id, update.status, update.note)
    if not result:
        raise HTTPException(status_code=404, detail="Finding not found")
    return result


@router.post("/security/scans/{scan_id}/rerun", response_model=ScanRun, status_code=201)
async def rerun_scan(scan_id: str, background_tasks: BackgroundTasks):
    db = await get_db()
    scan = await db.get_scan_run(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    source_ref = scan.get("source_ref") or scan["repo_url"]
    source_type = scan.get("source_type") or "repo"
    if source_type == "zip":
        raise HTTPException(status_code=422, detail="zip uploads cannot be re-run; upload the file again")
    if await db.active_scan_for_repo(source_ref):
        raise HTTPException(status_code=409, detail="A scan for this source is already queued or running")
    run = await db.insert("scan_runs", {
        "repo_url": source_ref,
        "name": scan.get("name"),
        "status": "queued",
        "source_type": source_type,
        "project_id": scan.get("project_id"),
        "source_ref": source_ref,
        "scan_options": scan.get("scan_options") or {},
        "scan_version": settings.SECURITY_SCAN_VERSION,
    })
    background_tasks.add_task(run_security_scan, run["id"], source_type, source_ref, scan.get("scan_options") or {})
    return run


def _compare_key(finding: dict) -> str:
    return _finding_id(
        "", finding.get("rule_id"), finding.get("file") or "", finding.get("line")
    )


@router.get("/security/projects/{project_id}/compare", response_model=ScanComparison)
async def compare_scans(
    project_id: str,
    base: str = Query(...),
    target: str = Query(...),
):
    db = await get_db()
    base_run = await db.get_scan_run(base)
    target_run = await db.get_scan_run(target)
    if not base_run or not target_run:
        raise HTTPException(status_code=404, detail="Scan not found")
    if base_run.get("project_id") != project_id or target_run.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="Scans must belong to the requested project")

    base_findings = {_compare_key(f): f for f in await db.get_scan_findings(base)}
    target_findings = {_compare_key(f): f for f in await db.get_scan_findings(target)}

    added, removed, status_changed = [], [], []
    unchanged = 0
    for key, finding in target_findings.items():
        item = CompareItem(
            key=key,
            severity=finding.get("severity", "low"),
            category=finding.get("category", "code"),
            file=finding.get("file", ""),
            line=finding.get("line"),
            title=finding.get("title"),
            base_status=base_findings.get(key, {}).get("status") if key in base_findings else None,
            target_status=finding.get("status"),
        )
        if key not in base_findings:
            added.append(item)
        elif base_findings[key].get("status") != finding.get("status"):
            status_changed.append(item)
        else:
            unchanged += 1
    for key, finding in base_findings.items():
        if key not in target_findings:
            removed.append(CompareItem(
                key=key,
                severity=finding.get("severity", "low"),
                category=finding.get("category", "code"),
                file=finding.get("file", ""),
                line=finding.get("line"),
                title=finding.get("title"),
                base_status=finding.get("status"),
                target_status=None,
            ))

    return ScanComparison(
        base_scan_id=base,
        target_scan_id=target,
        added=added,
        removed=removed,
        status_changed=status_changed,
        unchanged=unchanged,
    )