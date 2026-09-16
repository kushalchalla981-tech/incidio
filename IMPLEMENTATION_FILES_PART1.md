# Implementation Files - Part 1: Config, Database, Models

## backend/requirements.txt

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
supabase==2.3.4
python-dotenv==1.0.0
httpx==0.26.0
aiofiles==23.2.1
python-dateutil==2.8.2
```

---

## backend/.env.example

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
OPENAI_API_KEY=sk-your-key-here
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## backend/app/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()
```

---

## backend/app/database.py

```python
from supabase import create_client, Client
from app.config import settings
from typing import Optional

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client


async def check_db_health() -> bool:
    try:
        get_supabase_client().table("logs").select("id").limit(1).execute()
        return True
    except Exception:
        return False
```

---

## backend/app/models.py

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class LogCreate(BaseModel):
    timestamp: datetime
    service: str = Field(..., max_length=100)
    level: str
    message: str
    raw_log: str
    metadata: Optional[dict] = {}

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = v.upper()
        if v not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("Invalid log level")
        return v


class LogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    service: Optional[str]
    level: str
    message: str
    raw_log: str
    template_id: Optional[int] = None
    parameters: Optional[dict] = None
    metadata: dict = {}
    created_at: datetime


class LogBatchCreate(BaseModel):
    logs: List[LogCreate]


class LogUploadResponse(BaseModel):
    logs_processed: int
    logs_failed: int
    errors: List[str] = []


class IncidentCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    severity: str
    start_time: datetime
    affected_services: List[str] = []
    metadata: Optional[dict] = {}

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError("Invalid severity")
        return v


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("open", "investigating", "resolved", "closed"):
            raise ValueError("Invalid status")
        return v


class IncidentResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    severity: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    affected_services: List[str]
    root_cause: Optional[str]
    resolution: Optional[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
```

---

## All __init__.py files (empty)

Create these files with empty content:
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/api/v1/__init__.py`
- `backend/app/api/v1/routes/__init__.py`
