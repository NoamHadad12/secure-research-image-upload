"""API tests for authorized, short-lived upload download URLs."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base
from app.identity import (
    DANA_ID,
    DAVID_ID,
    HOSPITAL_A_ID,
    seed_development_identities,
)
from app.main import PRESIGNED_DOWNLOAD_URL_EXPIRY, create_app
from app.models import Upload, UploadStatus


@dataclass
class FakeObjectStorage:
    """Records GET signing calls so denied requests prove they never reach storage."""

    initialization_calls: int = 0
    presigned_get_calls: list[tuple[str, timedelta]] = field(default_factory=list)

    def ensure_private_bucket(self) -> None:
        self.initialization_calls += 1

    def presigned_get_url(self, *, object_key: str, expires: timedelta) -> str:
        self.presigned_get_calls.append((object_key, expires))
        return f"http://storage.test/{object_key}?temporary-download-signature"


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    yield factory

    Base.metadata.drop_all(engine)
    engine.dispose()


def _create_upload(*, status: UploadStatus) -> Upload:
    upload_id = uuid4()
    return Upload(
        id=upload_id,
        sample_id="download-sample",
        original_filename="download.png",
        classification="research",
        company_id=HOSPITAL_A_ID,
        object_key=f"uploads/{HOSPITAL_A_ID}/{upload_id}/download.png",
        content_type="image/png",
        status=status,
    )


def _seed_upload(session_factory: sessionmaker[Session], *, status: UploadStatus) -> Upload:
    with session_factory() as session:
        seed_development_identities(session)
        upload = _create_upload(status=status)
        session.add(upload)
        session.commit()
    return upload


def _make_client(
    session_factory: sessionmaker[Session], storage: FakeObjectStorage
) -> TestClient:
    return TestClient(
        create_app(
            Settings(frontend_origin="http://frontend.test"),
            session_factory=session_factory,
            storage=storage,
        )
    )


def test_hospital_a_can_get_a_one_minute_download_url_for_a_confirmed_upload(
    session_factory: sessionmaker[Session],
) -> None:
    upload = _seed_upload(session_factory, status=UploadStatus.COMPLETED)
    storage = FakeObjectStorage()
    client = _make_client(session_factory, storage)

    with client:
        response = client.post(
            f"/api/uploads/{upload.id}/download-url",
            headers={"X-User-ID": str(DANA_ID)},
        )

    assert response.status_code == 200
    assert response.json() == {
        "upload_id": str(upload.id),
        "download_url": f"http://storage.test/{upload.object_key}?temporary-download-signature",
        "download_url_expires_in_seconds": 60,
    }
    assert storage.presigned_get_calls == [(upload.object_key, PRESIGNED_DOWNLOAD_URL_EXPIRY)]


def test_hospital_b_cannot_get_a_download_url_for_hospital_a_upload(
    session_factory: sessionmaker[Session],
) -> None:
    upload = _seed_upload(session_factory, status=UploadStatus.COMPLETED)
    storage = FakeObjectStorage()
    client = _make_client(session_factory, storage)

    with client:
        foreign_response = client.post(
            f"/api/uploads/{upload.id}/download-url",
            headers={"X-User-ID": str(DAVID_ID)},
        )
        absent_response = client.post(
            f"/api/uploads/{uuid4()}/download-url",
            headers={"X-User-ID": str(DAVID_ID)},
        )

    assert foreign_response.status_code == absent_response.status_code == 404
    assert foreign_response.json() == absent_response.json() == {
        "error": {"code": "not_found", "message": "Upload not found"}
    }
    assert storage.presigned_get_calls == []


def test_pending_upload_cannot_receive_a_download_url(
    session_factory: sessionmaker[Session],
) -> None:
    upload = _seed_upload(session_factory, status=UploadStatus.PENDING_UPLOAD)
    storage = FakeObjectStorage()
    client = _make_client(session_factory, storage)

    with client:
        response = client.post(
            f"/api/uploads/{upload.id}/download-url",
            headers={"X-User-ID": str(DANA_ID)},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "request_error", "message": "Request could not be completed"}
    }
    assert storage.presigned_get_calls == []
