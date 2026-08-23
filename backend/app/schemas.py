"""Public API response schemas that contain no storage or credential details."""

from uuid import UUID

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class UploadInitiationResponse(BaseModel):
    """Public result for a pending direct-to-MinIO upload."""

    upload_id: UUID
    upload_url: str
    upload_url_expires_in_seconds: int


class UploadConfirmationResponse(BaseModel):
    """Public result after the backend verifies an uploaded MinIO object."""

    upload_id: UUID
    status: str
