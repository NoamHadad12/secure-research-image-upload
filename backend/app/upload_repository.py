"""Tenant-scoped persistence operations for upload metadata."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Upload


def add_upload(session: Session, *, upload: Upload) -> Upload:
    """Add and flush an upload while leaving transaction ownership to the caller."""

    session.add(upload)
    session.flush()
    return upload


def list_uploads_for_company(session: Session, *, company_id: UUID) -> list[Upload]:
    """Return only the uploads owned by one company, filtered by SQL."""

    statement = (
        select(Upload)
        .where(Upload.company_id == company_id)
        .order_by(Upload.created_at.desc(), Upload.id.desc())
    )
    return list(session.scalars(statement))


def get_upload_for_company(
    session: Session,
    *,
    upload_id: UUID,
    company_id: UUID,
) -> Upload | None:
    """Return an owned upload or None for both foreign and absent identifiers."""

    statement = select(Upload).where(
        Upload.id == upload_id,
        Upload.company_id == company_id,
    )
    return session.scalar(statement)
