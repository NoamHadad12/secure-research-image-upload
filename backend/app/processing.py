"""Local, non-durable processing simulation for confirmed research uploads."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionFactory
from app.models import Upload, UploadStatus

UploadProcessor = Callable[[Upload], None]
StatusObserver = Callable[[UploadStatus], None]


def simulate_image_processing(_: Upload) -> None:
    """Placeholder for image analysis work that belongs in a worker in production."""


def _transition(
    session: Session,
    upload: Upload,
    status: UploadStatus,
    on_transition: StatusObserver | None,
) -> None:
    upload.status = status
    session.commit()
    if on_transition is not None:
        on_transition(status)


def process_confirmed_upload(
    session_factory: SessionFactory,
    upload_id: UUID,
    *,
    process_upload: UploadProcessor = simulate_image_processing,
    on_transition: StatusObserver | None = None,
) -> None:
    """Advance one confirmed upload using a new database session for background work."""

    with session_factory() as session:
        upload = session.get(Upload, upload_id)
        if upload is None or upload.status is not UploadStatus.UPLOADED:
            return

        try:
            _transition(session, upload, UploadStatus.QUEUED, on_transition)
            _transition(session, upload, UploadStatus.PROCESSING, on_transition)
            process_upload(upload)
            _transition(session, upload, UploadStatus.COMPLETED, on_transition)
        except Exception:
            session.rollback()
            failed_upload = session.get(Upload, upload_id)
            if failed_upload is None:
                return
            _transition(session, failed_upload, UploadStatus.FAILED, on_transition)
