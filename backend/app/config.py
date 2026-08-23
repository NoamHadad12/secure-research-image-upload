"""Validated application configuration."""

from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings supplied by the environment in local and containerized runs."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Secure Research Image Upload API"
    app_version: str = "0.1.0"
    frontend_origin: AnyHttpUrl = "http://localhost:5173"
    database_url: str | None = None

    @field_validator("frontend_origin")
    @classmethod
    def require_origin_without_path(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Accept an HTTP origin, not an arbitrary URL with a resource path."""

        if value.path not in {"", "/"} or value.query or value.fragment:
            raise ValueError("FRONTEND_ORIGIN must be an origin without a path")
        return value

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
