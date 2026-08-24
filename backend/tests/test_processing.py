"""PostgreSQL-backed tests for the local upload-processing simulation."""

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.identity import HOSPITAL_A_ID, seed_development_identities
from app.models import Upload, UploadStatus
from app.processing import process_confirmed_upload


@dataclass
class TrackingSessionFactory:
    """Records that the processor obtains its own database session."""

    factory: sessionmaker[Session]
    calls: int = 0

    def __call__(self) -> Session:
        self.calls += 1
        return self.factory()


@pytest.fixture(scope="module")
def postgres_engine() -> Iterator[Engine]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL processing coverage")

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def create_uploaded_upload(postgres_engine: Engine) -> Iterator[Callable[[], Upload]]:
    created_upload_ids: list[UUID] = []

    def create() -> Upload:
        upload_id = uuid4()
        upload = Upload(
            id=upload_id,
            sample_id=f"processing-{upload_id}",
            original_filename="processing.png",
            classification="research",
            company_id=HOSPITAL_A_ID,
            object_key=f"uploads/{HOSPITAL_A_ID}/{upload_id}/processing.png",
            content_type="image/png",
            size_bytes=512,
            etag="processing-etag",
            status=UploadStatus.UPLOADED,
        )
        with Session(postgres_engine, expire_on_commit=False) as session:
            seed_development_identities(session)
            session.add(upload)
            session.commit()
        created_upload_ids.append(upload_id)
        return upload

    yield create

    if created_upload_ids:
        with Session(postgres_engine) as session:
            session.execute(delete(Upload).where(Upload.id.in_(created_upload_ids)))
            session.commit()


def test_processor_uses_a_new_session_and_completes_all_transitions(
    postgres_engine: Engine,
    create_uploaded_upload: Callable[[], Upload],
) -> None:
    upload = create_uploaded_upload()
    session_factory = TrackingSessionFactory(sessionmaker(bind=postgres_engine))
    transitions: list[UploadStatus] = []

    process_confirmed_upload(
        session_factory,
        upload.id,
        on_transition=transitions.append,
    )

    assert session_factory.calls == 1
    assert transitions == [
        UploadStatus.QUEUED,
        UploadStatus.PROCESSING,
        UploadStatus.COMPLETED,
    ]
    with Session(postgres_engine) as session:
        processed_upload = session.get(Upload, upload.id)

    assert processed_upload is not None
    assert processed_upload.status is UploadStatus.COMPLETED


def test_processor_exception_persists_failed_status(
    postgres_engine: Engine,
    create_uploaded_upload: Callable[[], Upload],
) -> None:
    upload = create_uploaded_upload()
    session_factory = TrackingSessionFactory(sessionmaker(bind=postgres_engine))
    transitions: list[UploadStatus] = []

    def fail_processing(_: Upload) -> None:
        raise RuntimeError("simulated processor failure")

    process_confirmed_upload(
        session_factory,
        upload.id,
        process_upload=fail_processing,
        on_transition=transitions.append,
    )

    assert session_factory.calls == 1
    assert transitions == [
        UploadStatus.QUEUED,
        UploadStatus.PROCESSING,
        UploadStatus.FAILED,
    ]
    with Session(postgres_engine) as session:
        processed_upload = session.get(Upload, upload.id)

    assert processed_upload is not None
    assert processed_upload.status is UploadStatus.FAILED
