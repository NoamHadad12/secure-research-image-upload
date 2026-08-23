"""Public API response schemas that contain no storage or credential details."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
