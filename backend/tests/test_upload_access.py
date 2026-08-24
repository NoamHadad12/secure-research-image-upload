"""API tests for tenant-isolated upload list and detail routes."""

from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

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
    HOSPITAL_B_ID,
    seed_development_identities,
)
from app.main import create_app
from app.models import Upload, UploadStatus


@dataclass
class FakeObjectStorage:
    """No storage access is needed to list or retrieve metadata."""

    initialization_calls: int = 0

    def ensure_private_bucket(self) -> None:
        self.initialization_calls += 1


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


def _create_upload(*, company_id: UUID, filename: str) -> Upload:
    upload_id = uuid4()
    return Upload(
        id=upload_id,
        sample_id=f"sample-{filename}",
        original_filename=filename,
        classification="research",
        company_id=company_id,
        object_key=f"uploads/{company_id}/{upload_id}/{filename}",
        content_type="image/png",
        status=UploadStatus.COMPLETED,
        size_bytes=512,
        etag="private-storage-etag",
    )


def _seed_uploads(session_factory: sessionmaker[Session]) -> tuple[Upload, Upload]:
    with session_factory() as session:
        seed_development_identities(session)
        hospital_a_upload = _create_upload(company_id=HOSPITAL_A_ID, filename="hospital-a.png")
        hospital_b_upload = _create_upload(company_id=HOSPITAL_B_ID, filename="hospital-b.png")
        session.add_all([hospital_a_upload, hospital_b_upload])
        session.commit()
    return hospital_a_upload, hospital_b_upload


def _make_client(session_factory: sessionmaker[Session]) -> TestClient:
    return TestClient(
        create_app(
            Settings(frontend_origin="http://frontend.test"),
            session_factory=session_factory,
            storage=FakeObjectStorage(),
        )
    )


def test_hospital_a_can_list_and_retrieve_its_own_public_upload_metadata(
    session_factory: sessionmaker[Session],
) -> None:
    hospital_a_upload, _ = _seed_uploads(session_factory)
    client = _make_client(session_factory)

    with client:
        list_response = client.get("/api/uploads", headers={"X-User-ID": str(DANA_ID)})
        detail_response = client.get(
            f"/api/uploads/{hospital_a_upload.id}",
            headers={"X-User-ID": str(DANA_ID)},
        )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body == list_response.json()[0]
    assert body["upload_id"] == str(hospital_a_upload.id)
    assert body["sample_id"] == hospital_a_upload.sample_id
    assert body["filename"] == "hospital-a.png"
    assert body["classification"] == "research"
    assert body["status"] == "completed"
    assert "created_at" in body
    assert "object_key" not in body
    assert "company_id" not in body
    assert "etag" not in body


def test_hospital_b_cannot_list_or_retrieve_hospital_a_metadata(
    session_factory: sessionmaker[Session],
) -> None:
    hospital_a_upload, hospital_b_upload = _seed_uploads(session_factory)
    client = _make_client(session_factory)

    with client:
        list_response = client.get("/api/uploads", headers={"X-User-ID": str(DAVID_ID)})
        foreign_response = client.get(
            f"/api/uploads/{hospital_a_upload.id}",
            headers={"X-User-ID": str(DAVID_ID)},
        )
        absent_response = client.get(
            f"/api/uploads/{uuid4()}",
            headers={"X-User-ID": str(DAVID_ID)},
        )

    assert list_response.status_code == 200
    assert [record["upload_id"] for record in list_response.json()] == [str(hospital_b_upload.id)]
    assert foreign_response.status_code == absent_response.status_code == 404
    assert foreign_response.json() == absent_response.json() == {
        "error": {"code": "not_found", "message": "Upload not found"}
    }
