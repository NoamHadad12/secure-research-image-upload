"""Validated application configuration."""

from functools import lru_cache

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings supplied by the environment in local and containerized runs."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Secure Research Image Upload API"
    app_version: str = "0.1.0"
    frontend_origin: AnyHttpUrl = "http://localhost:5173"
    database_url: str | None = None
    minio_bucket: str = "research-images"
    minio_region: str = "us-east-1"
    minio_internal_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_root_user: str | None = None
    minio_root_password: SecretStr | None = None

    @field_validator("frontend_origin")
    @classmethod
    def require_origin_without_path(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Accept an HTTP origin, not an arbitrary URL with a resource path."""

        if value.path not in {"", "/"} or value.query or value.fragment:
            raise ValueError("FRONTEND_ORIGIN must be an origin without a path")
        return value

    @field_validator("minio_bucket", "minio_region")
    @classmethod
    def require_non_empty_minio_identifier(cls, value: str) -> str:
        """Reject empty bucket and region values before the storage client starts."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("MinIO bucket and region values must not be empty")
        return normalized_value

    @field_validator("minio_internal_endpoint", "minio_public_endpoint")
    @classmethod
    def require_minio_host_port(cls, value: str) -> str:
        """Accept only an SDK endpoint, not a URL that could be rewritten later."""

        normalized_value = value.strip()
        if not normalized_value or "://" in normalized_value or "/" in normalized_value:
            raise ValueError("MinIO endpoints must use host:port without a URL scheme or path")
        return normalized_value

    @property
    def normalized_frontend_origin(self) -> str:
        """Return the serialized origin in the form expected by CORS."""

        return str(self.frontend_origin).rstrip("/")

    @property
    def required_database_url(self) -> str:
        """Return the database URL or fail clearly when persistence is required."""

        if not self.database_url:
            raise RuntimeError("DATABASE_URL must be configured before starting the API")
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Create settings once per process after Pydantic validates environment input."""

    return Settings()
