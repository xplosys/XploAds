"""Application settings. Every variable is documented in /.env.example and docs/deployment/ENVIRONMENT.md."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "XploAds"
    log_level: str = "INFO"

    # Database: the API and workers connect as the non-owner, NOBYPASSRLS role.
    database_url: str = "postgresql+asyncpg://xploads_app:xploads_app@localhost:5432/xploads"
    # Migrations connect as the schema owner.
    migration_database_url: str = "postgresql+psycopg://xploads_owner:xploads_owner@localhost:5432/xploads"
    app_db_role: str = "xploads_app"
    db_pool_size: int = 10

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None

    # Auth
    jwt_secret: str = Field(default="change-me-local-only-secret-at-least-32-bytes", min_length=32)
    jwt_issuer: str = "xploads"
    jwt_audience: str = "xploads-api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30
    email_verification_ttl_hours: int = 48
    password_reset_ttl_minutes: int = 30
    mfa_challenge_ttl_minutes: int = 5
    invitation_ttl_days: int = 7
    max_failed_logins: int = 10
    lockout_minutes: int = 15

    # Base64url-encoded 32-byte key-encryption key. In production supply it from a secret manager / KMS.
    data_encryption_key: str = "bG9jYWwtZGV2LW9ubHkta2V5LWRvLW5vdC11c2UtISE="

    cookie_secure: bool = False
    cookie_domain: str | None = None
    refresh_cookie_name: str = "xploads_refresh"

    frontend_url: str = "http://localhost:3000"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Notifications
    email_mode: Literal["console", "smtp"] = "console"
    email_from: str = "XploAds <no-reply@xploads.local>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    # Object storage. "local" stores files on disk behind HMAC-signed API URLs (development and tests);
    # "s3" talks to any S3-compatible service (AWS S3, Cloudflare R2, SeaweedFS, MinIO).
    storage_backend: Literal["local", "s3"] = "local"
    storage_bucket: str = "xploads-assets"
    storage_local_path: str = "./var/storage"
    s3_endpoint_url: str | None = None
    # Endpoint the browser uses for signed URLs when it differs from the one the API uses (e.g. SeaweedFS in Docker).
    s3_public_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_force_path_style: bool = True
    storage_upload_url_ttl_seconds: int = 900
    storage_download_url_ttl_seconds: int = 300
    # Base URL for the local backend's signed URLs. Empty = same origin as the web app (relative /api/v1/...).
    api_public_url: str = ""

    rate_limit_enabled: bool = True
    max_request_body_bytes: int = 1_048_576

    sentry_dsn: str | None = None

    @field_validator("data_encryption_key", mode="before")
    @classmethod
    def _default_key(cls, v: object) -> object:
        # An empty value falls back to the development key, which staging/production refuse to boot with.
        return v or cls.model_fields["data_encryption_key"].default

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def is_production(self) -> bool:
        return self.environment in ("staging", "production")

    def assert_safe_for_environment(self) -> None:
        """Refuse to boot staging/production with development defaults."""
        if not self.is_production:
            return
        problems = []
        if "change-me" in self.jwt_secret:
            problems.append("JWT_SECRET uses the development default")
        if self.data_encryption_key == Settings.model_fields["data_encryption_key"].default:
            problems.append("DATA_ENCRYPTION_KEY uses the development default")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if self.email_mode == "console":
            problems.append("EMAIL_MODE=console is not allowed")
        if self.storage_backend == "local":
            problems.append("STORAGE_BACKEND=local is not allowed; use s3 (AWS S3, Cloudflare R2, SeaweedFS)")
        if "change-me" in (self.s3_secret_access_key or ""):
            problems.append("S3_SECRET_ACCESS_KEY uses the example value")
        if problems:
            raise RuntimeError("Unsafe configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
