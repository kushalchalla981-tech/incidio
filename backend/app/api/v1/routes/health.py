from datetime import datetime, timezone

from fastapi import APIRouter

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
