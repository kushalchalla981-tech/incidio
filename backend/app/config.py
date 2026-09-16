import json
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]
    LLM_MODEL: str = "gpt-4o-mini"
    SCAN_TMP_DIR: str = "./.scan-tmp"
    MAX_REPO_SIZE_MB: int = 50
    MAX_SCAN_FILES: int = 2000
    MAX_LLM_FILES: int = 10
    MAX_LLM_FILE_CHARS: int = 12000
    MAX_LLM_INPUT_CHARS: int = 600000
    SCAN_ALLOWED_HOSTS: Annotated[list[str], NoDecode] = ["github.com", "gitlab.com", "bitbucket.org"]
    SCAN_MAX_CONCURRENT: int = 2
    MAX_ZIP_MB: int = 50
    MAX_ZIP_ENTRIES: int = 5000
    URL_CHECK_TIMEOUT: float = 10.0
    URL_ALLOW_PRIVATE_IP: bool = False
    OSV_API_ENABLED: bool = False
    SECURITY_SCAN_VERSION: str = "1.0.0"

    @field_validator("CORS_ORIGINS", "SCAN_ALLOWED_HOSTS", mode="before")
    @classmethod
    def _split_list(cls, v: object) -> object:
        if isinstance(v, str):
            if v.lstrip().startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def cors_allow_credentials(self) -> bool:
        """Credentials are only sent when CORS origins are explicitly configured."""
        return "*" not in self.CORS_ORIGINS


settings = Settings()
