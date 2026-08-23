"""PostgreSQL metadata models. Object bytes remain in MinIO, not these tables."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UploadStatus(str, Enum):
    """Lifecycle states for a research image upload."""

    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TimestampMixin:
    """Server-managed timestamps for auditable metadata."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Company(Base):
    """A company that owns users and research-upload metadata."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="company")
    uploads: Mapped[list["Upload"]] = relationship(back_populates="company")


class User(Base):
    """A development user whose company is resolved server-side."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    company: Mapped[Company] = relationship(back_populates="users")


class Upload(TimestampMixin, Base):
    """Structured metadata for a private object stored separately in MinIO."""

    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        SqlEnum(UploadStatus, name="upload_status"),
        default=UploadStatus.PENDING_UPLOAD,
        server_default=UploadStatus.PENDING_UPLOAD.value,
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company: Mapped[Company] = relationship(back_populates="uploads")
