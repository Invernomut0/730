"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for local-first HealthDocs deployments."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://healthdocs:healthdocs@postgres:5432/healthdocs"
    redis_url: str = "redis://redis:6379/0"
    storage_root: Path = Path("/data")
    watch_directory: Path = Path("/data/inbox")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_upload_request_overhead_bytes: int = Field(default=64 * 1024, ge=0)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    auth_enabled: bool = False
    auth_password_hash: str = ""
    session_secret: str = ""
    login_rate_limit_attempts: int = Field(default=5, gt=0)
    login_rate_limit_window_seconds: int = Field(default=900, gt=0)
    backup_root: Path = Path("/backups")
    backup_encryption_key: str = ""
    google_drive_access_token: str = ""
    google_drive_folder_id: str = ""

    lmstudio_base_url: HttpUrl = "http://host.docker.internal:1234/v1"
    lmstudio_api_token: str = ""
    lmstudio_main_model: str = ""
    lmstudio_simple_model: str = "qwen/qwen3-vl-8b"
    lmstudio_extraction_model: str = "qwen/qwen3-vl-8b"
    lmstudio_fallback_model: str = "qwen3.8-27b-abliterated-mtplx-optimized-speed"
    lmstudio_relation_model: str = "qwen3.8-27b-abliterated-mtplx-optimized-speed"
    lmstudio_vision_model: str = ""
    lmstudio_embedding_model: str = ""
    lmstudio_request_timeout_seconds: int = Field(default=1800, gt=0)
    rizzo_flow_enabled: bool = False
    rizzo_flow_base_url: HttpUrl | None = None

    medical_event_lookback_days: int = Field(default=365, gt=0)
    auto_confirm_threshold: float = Field(default=0.95, ge=0, le=1)
    suggest_threshold: float = Field(default=0.75, ge=0, le=1)
    aifa_update_interval_days: int = Field(default=7, gt=0)
    aifa_catalog_path: Path = Path("/data/aifa/catalog.csv")

    @property
    def originals_root(self) -> Path:
        return self.storage_root / "originals"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
