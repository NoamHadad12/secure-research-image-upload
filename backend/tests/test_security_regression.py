"""Assignment-mandated API security regression coverage."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.config import Settings
from app.db import Base
from app.identity import DANA_ID, DAVID_ID, HOSPITAL_A_ID, HOSPITAL_B_ID
from app.main import create_app
from app.models import Upload, UploadStatus


@dataclass
class SecurityRegressionStorage:
    """Captures signing calls so authorization failures cannot reach MinIO."""

    initialization_calls: int = 0
    presigned_put_calls: list[tuple[str, timedelta]] = field(default_factory=list)
    presigned_get_calls: list[tuple[str, timedelta]] = field(default_factory=list)

    def ensure_private_bucket(self) -> None:
        self.initialization_calls += 1

    def presigned_put_url(self, *, object_key: str, expires: timedelta) -> str:
        self.presigned_put_calls.append((object_key, expires))
        return f"http://storage.test/{object_key}?temporary-upload-signature"

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


def _make_client(
    session_factory: sessionmaker[Session],
) -> tuple[TestClient, SecurityRegressionStorage]:
    storage = SecurityRegressionStorage()
    client = TestClient(
        create_app(
            Settings(frontend_origin="http://frontend.test"),
            session_factory=session_factory,
            storage=storage,
        )
    )
    return client, storage


def _valid_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "sample_id": "security-sample",
        "filename": "security-image.png",
        "classification": "research",
        "content_type": "image/png",
    }
    metadata.update(overrides)
    return metadata


def _create_hospital_a_upload(client: TestClient) -> UUID:
    response = client.post(
        "/api/uploads/initiate",
        headers={"X-User-ID": str(DANA_ID)},
        json=_valid_metadata(),
    )
    assert response.status_code == 201
    return UUID(response.json()["upload_id"])


def test_assignment_requirement_hospital_a_can_create_and_access_its_own_upload(
    session_factory: sessionmaker[Session],
) -> None:
    client, storage = _make_client(session_factory)

    with client:
        upload_id = _create_hospital_a_upload(client)
        response = client.get(
            f"/api/uploads/{upload_id}",
            headers={"X-User-ID": str(DANA_ID)},
        )

    assert response.status_code == 200
    assert response.json()["upload_id"] == str(upload_id)
    assert response.json()["sample_id"] == "security-sample"
    assert "object_key" not in response.json()
    assert len(storage.presigned_put_calls) == 1

    with session_factory() as session:
        upload = session.get(Upload, upload_id)

    assert upload is not None
    assert upload.company_id == HOSPITAL_A_ID


def test_assignment_requirement_hospital_b_is_denied_hospital_a_upload_access(
    session_factory: sessionmaker[Session],
) -> None:
    client, _ = _make_client(session_factory)

    with client:
        upload_id = _create_hospital_a_upload(client)
        list_response = client.get("/api/uploads", headers={"X-User-ID": str(DAVID_ID)})
        foreign_response = client.get(
            f"/api/uploads/{upload_id}",
            headers={"X-User-ID": str(DAVID_ID)},
        )
        absent_response = client.get(
            f"/api/uploads/{uuid4()}",
            headers={"X-User-ID": str(DAVID_ID)},
        )

    assert list_response.status_code == 200
    assert all(record["upload_id"] != str(upload_id) for record in list_response.json())
    assert foreign_response.status_code == absent_response.status_code == 404
    assert foreign_response.json() == absent_response.json() == {
        "error": {"code": "not_found", "message": "Upload not found"}
    }


def test_assignment_requirement_hospital_b_cannot_get_hospital_a_download_url(
    session_factory: sessionmaker[Session],
) -> None:
    client, storage = _make_client(session_factory)

    with client:
        upload_id = _create_hospital_a_upload(client)
        with session_factory() as session:
            upload = session.get(Upload, upload_id)
            assert upload is not None
            upload.status = UploadStatus.COMPLETED
            session.commit()

        response = client.post(
            f"/api/uploads/{upload_id}/download-url",
            headers={"X-User-ID": str(DAVID_ID)},
        )

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Upload not found"}}
    assert storage.presigned_get_calls == []


@pytest.mark.parametrize(
    "metadata",
    [
        _valid_metadata(sample_id=""),
        _valid_metadata(classification="unrecognized"),
        _valid_metadata(company_id=str(HOSPITAL_B_ID)),
        _valid_metadata(object_key="uploads/forged-company/forged-upload/forged.png"),
        _valid_metadata(
            company_id=str(HOSPITAL_B_ID),
            object_key="uploads/forged-company/forged-upload/forged.png",
        ),
    ],
)
def test_assignment_requirement_invalid_or_missing_metadata_is_rejected(
    session_factory: sessionmaker[Session],
    metadata: dict[str, object],
) -> None:
    client, storage = _make_client(session_factory)

    with client:
        response = client.post(
            "/api/uploads/initiate",
            headers={"X-User-ID": str(DANA_ID)},
            json=metadata,
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "Request validation failed"}
    }
    assert storage.presigned_put_calls == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Upload)) == 0
