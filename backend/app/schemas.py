"""Public API response schemas that contain no storage or credential details."""

from datetime import datetime
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


class UploadRecordResponse(BaseModel):
    """Tenant-visible upload metadata, deliberately excluding the object key."""

    upload_id: UUID
    sample_id: str
    filename: str
    classification: str
    status: str
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    """A short-lived GET capability for an upload the caller already owns."""

    upload_id: UUID
    download_url: str
    download_url_expires_in_seconds: int
