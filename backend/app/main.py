import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import get_db
from app.api.v1.routes import health, logs, incidents, anomalies, search, scans, security
from app.middleware import SecurityHeadersMiddleware
from app.services.parser import get_miner
from app.services.scanner import sweep_orphaned_scans

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = None
    try:
        db = await get_db()
        await sweep_orphaned_scans()
    except Exception as exc:
        if settings.ENVIRONMENT == "production":
            logger.error(
                "Startup failed: the database could not be reached (%s). "
                "Refusing to start in production without a database.",
                exc,
            )
            raise
        logger.warning(
            "Database unavailable during startup (%s); continuing in %s mode. "
            "Health checks will report the database as disconnected.",
            exc,
            settings.ENVIRONMENT,
        )
    else:
        get_miner()
    yield
    if db is not None:
        await db.close()


app = FastAPI(
    title="AI Incident Copilot",
    description="Intelligent incident management for small software teams",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.ENVIRONMENT == "production" and "*" in settings.CORS_ORIGINS:
    logger.warning(
        "CORS is configured with wildcard origins in production; set "
        "CORS_ORIGINS to explicit origins for credentialed requests."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router, tags=["health"])
app.include_router(logs.router, prefix=settings.API_V1_PREFIX, tags=["logs"])
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX, tags=["incidents"])
app.include_router(anomalies.router, prefix=settings.API_V1_PREFIX, tags=["anomalies"])
app.include_router(search.router, prefix=settings.API_V1_PREFIX, tags=["search"])
app.include_router(scans.router, prefix=settings.API_V1_PREFIX, tags=["scans"])
app.include_router(security.router, prefix=settings.API_V1_PREFIX, tags=["security"])
