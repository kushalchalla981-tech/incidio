from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.models import AnomalyDetectionRequest, AnomalyDetectionResult, AnomalyWindow
from app.services.anomaly import detect_anomalies

router = APIRouter()


@router.post("/anomalies/detect", response_model=AnomalyDetectionResult)
async def detect_anomalies_endpoint(params: AnomalyDetectionRequest):
    db = await get_db()
    logs = await db.query_logs_range(
        service=params.service,
        start_time=params.start_time.isoformat() if params.start_time else None,
        end_time=params.end_time.isoformat() if params.end_time else None,
    )
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found in the specified range")

    windows = detect_anomalies(
        logs=logs,
        window_minutes=params.window_minutes,
        contamination=params.contamination,
    )

    anomaly_windows = [w for w in windows if w["is_anomaly"]]
    return AnomalyDetectionResult(
        windows=[AnomalyWindow(**w) for w in windows],
        total_windows=len(windows),
        anomalous_windows=len(anomaly_windows),
        contamination=params.contamination,
    )


@router.get("/anomalies/detect")
async def detect_anomalies_get(
    service: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    window_minutes: int = Query(1, ge=1, le=1440),
    contamination: float = Query(0.1, ge=0.01, le=0.5),
):
    db = await get_db()
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else None
    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else None

    logs = await db.query_logs_range(
        service=service or None,
        start_time=start_dt.isoformat() if start_dt else None,
        end_time=end_dt.isoformat() if end_dt else None,
    )
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found in the specified range")

    windows = detect_anomalies(
        logs=logs,
        window_minutes=window_minutes,
        contamination=contamination,
    )

    anomaly_windows = [w for w in windows if w["is_anomaly"]]
    return AnomalyDetectionResult(
        windows=[AnomalyWindow(**w) for w in windows],
        total_windows=len(windows),
        anomalous_windows=len(anomaly_windows),
        contamination=contamination,
    )
