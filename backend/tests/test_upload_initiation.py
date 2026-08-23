from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base
from app.identity import ALICE_ID, HOSPITAL_A_ID
from app.main import PRESIGNED_UPLOAD_URL_EXPIRY, create_app
from app.models import Upload, UploadStatus


@dataclass
class FakeObjectStorage:
    initialization_calls: int = 0
    presigned_put_calls: list[tuple[str, timedelta]] = field(default_factory=list)

    def ensure_private_bucket(self) -> None:
        self.initialization_calls += 1

    def presigned_put_url(self, *, object_key: str, expires: timedelta) -> str:
        self.presigned_put_calls.append((object_key, expires))
        return f"http://storage.test/{object_key}?temporary-signature"


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


def make_client(
    session_factory: sessionmaker[Session],
) -> tuple[TestClient, FakeObjectStorage]:
    storage = FakeObjectStorage()
    app = create_app(
        Settings(frontend_origin="http://frontend.test"),
        session_factory=session_factory,
        storage=storage,
    )
    return TestClient(app), storage


def initiation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sample_id": "sample-17",
        "filename": "research image.png",
        "classification": "research",
        "content_type": "image/png",
    }
    payload.update(overrides)
    return payload


def test_hospital_a_initiation_creates_pending_upload_and_returns_only_public_values(
    session_factory: sessionmaker[Session],
) -> None:
    client, storage = make_client(session_factory)

    with client:
        response = client.post(
            "/api/uploads/initiate",
            headers={
                "X-User-ID": str(ALICE_ID),
                "X-Company-ID": "00000000-0000-0000-0000-0000000000b1",
            },
            json=initiation_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"upload_id", "upload_url", "upload_url_expires_in_seconds"}
    assert body["upload_url_expires_in_seconds"] == 300
    assert "object_key" not in body
    assert "company_id" not in body
    assert "secret" not in body["upload_url"]

    with session_factory() as session:
        upload = session.get(Upload, UUID(body["upload_id"]))

    assert upload is not None
    assert upload.company_id == HOSPITAL_A_ID
    assert upload.status == UploadStatus.PENDING_UPLOAD
    assert upload.object_key == f"uploads/{HOSPITAL_A_ID}/{upload.id}/research-image.png"
    assert storage.presigned_put_calls == [
        (upload.object_key, PRESIGNED_UPLOAD_URL_EXPIRY),
    ]


def test_invalid_initiation_metadata_is_rejected_before_storage_or_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    client, storage = make_client(session_factory)

    with client:
        response = client.post(
            "/api/uploads/initiate",
            headers={"X-User-ID": str(ALICE_ID)},
            json=initiation_payload(object_key="uploads/forged/object.png"),
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
        }
    }
    assert storage.presigned_put_calls == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Upload)) == 0
