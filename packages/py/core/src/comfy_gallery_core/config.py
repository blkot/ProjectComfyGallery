from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration loaded from CG_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CG_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://comfygallery:comfygallery@localhost:5432/comfygallery"
    redis_url: str = "redis://localhost:6379/0"
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    session_cookie_secure: bool = False
    session_ttl_hours: int = Field(default=168, ge=1, le=24 * 365)
    login_attempt_limit: int = Field(default=8, ge=2, le=100)
    login_attempt_window_seconds: int = Field(default=300, ge=30, le=3600)
    allowed_origins: str = "http://localhost:8080,http://localhost:5173"
    log_level: str = "INFO"
    managed_root: Path = Path("./data/managed")
    staging_root: Path = Path("./data/staging")
    export_root: Path = Path("./data/exports")
    backup_root: Path = Path("./data/backups")
    runtime_root: Path = Path("./data/runtime")
    allowed_source_roots: str = "./data/import"
    max_upload_bytes: int = Field(default=128 * 1024 * 1024, ge=1024)
    max_variant_upload_bytes: int = Field(default=512 * 1024 * 1024, ge=1024)
    hash_chunk_bytes: int = Field(default=1024 * 1024, ge=64 * 1024, le=16 * 1024 * 1024)
    minimum_free_bytes: int = Field(default=512 * 1024 * 1024, ge=0)
    thumbnail_max_dimension: int = Field(default=768, ge=128, le=4096)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    spatial_variant_validation_timeout_seconds: int = Field(default=60, ge=5, le=600)
    spatial_variant_duration_tolerance_seconds: float = Field(default=0.5, ge=0, le=30)
    spatial_variant_duration_tolerance_ratio: float = Field(default=0.01, ge=0, le=1)
    workflow_metadata_max_bytes: int = Field(
        default=64 * 1024 * 1024,
        ge=1024 * 1024,
        le=512 * 1024 * 1024,
    )
    workflow_json_max_depth: int = Field(default=128, ge=8, le=512)
    workflow_json_max_items: int = Field(default=250_000, ge=1_000, le=2_000_000)
    workflow_max_nodes: int = Field(default=20_000, ge=100, le=250_000)
    comfyui_base_url: str | None = None
    registry_http_timeout_seconds: float = Field(default=180.0, ge=5.0, le=600.0)
    registry_max_response_bytes: int = Field(
        default=64 * 1024 * 1024,
        ge=1024 * 1024,
        le=512 * 1024 * 1024,
    )
    registry_max_node_definitions: int = Field(default=20_000, ge=100, le=100_000)
    registry_metadata_concurrency: int = Field(default=4, ge=1, le=8)
    worker_heartbeat_interval_seconds: int = Field(default=15, ge=5, le=300)
    worker_stale_after_seconds: int = Field(default=90, ge=15, le=3600)
    job_stale_after_seconds: int = Field(default=1800, ge=60, le=86_400)
    queued_job_recovery_after_seconds: int = Field(default=60, ge=10, le=3600)
    running_job_recovery_after_seconds: int = Field(default=300, ge=30, le=86_400)
    scan_actor_time_limit_seconds: int = Field(default=0, ge=0, le=7 * 24 * 60 * 60)
    backup_expected_interval_hours: int = Field(default=30, ge=1, le=24 * 31)
    disk_warning_percent: float = Field(default=90.0, ge=1.0, le=99.9)

    session_cookie_name: str = "cg_session"
    csrf_cookie_name: str = "cg_csrf"

    @field_validator("admin_username")
    @classmethod
    def normalize_admin_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("admin username cannot be empty")
        return normalized

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("comfyui_base_url", mode="before")
    @classmethod
    def normalize_comfyui_base_url(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().rstrip("/")
        return normalized or None

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def allowed_source_root_paths(self) -> list[Path]:
        return [
            Path(value.strip()).expanduser().resolve()
            for value in self.allowed_source_roots.split(",")
            if value.strip()
        ]

    @property
    def resolved_managed_root(self) -> Path:
        return self.managed_root.expanduser().resolve()

    @property
    def resolved_staging_root(self) -> Path:
        return self.staging_root.expanduser().resolve()

    @property
    def resolved_export_root(self) -> Path:
        return self.export_root.expanduser().resolve()

    @property
    def resolved_backup_root(self) -> Path:
        return self.backup_root.expanduser().resolve()

    @property
    def resolved_runtime_root(self) -> Path:
        return self.runtime_root.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
