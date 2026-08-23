"""PostgreSQL-backed API coverage for secure upload confirmation."""

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.identity import ALICE_ID, BOB_ID, HOSPITAL_A_ID, seed_development_identities
from app.main import create_app
from app.models import Upload, UploadStatus
from app.storage import ObjectMissingError, ObjectStat

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass
class FakeObjectStorage:
    object_stats: dict[str, ObjectStat] = field(default_factory=dict)
    initialization_calls: int = 0
    stat_calls: list[str] = field(default_factory=list)

    def ensure_private_bucket(self) -> None:
        self.initialization_calls += 1

    def presigned_put_url(self, **_: object) -> str:
        raise AssertionError("Confirmation must not create a presigned upload URL")

    def stat_object(self, *, object_key: str) -> ObjectStat:
        self.stat_calls.append(object_key)
        try:
            return self.object_stats[object_key]
        except KeyError as error:
            raise ObjectMissingError from error


@pytest.fixture(scope="module")
def postgres_engine() -> Iterator[Engine]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL confirmation coverage")

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def create_pending_upload(postgres_engine: Engine) -> Iterator[Callable[..., Upload]]:
    created_upload_ids: list[UUID] = []

    def create(*, company_id: UUID = HOSPITAL_A_ID) -> Upload:
        upload_id = uuid4()
        upload = Upload(
            id=upload_id,
            sample_id=f"confirmation-{upload_id}",
            original_filename="confirmation.png",
            classification="research",
            company_id=company_id,
            object_key=f"uploads/{company_id}/{upload_id}/confirmation.png",
            content_type="image/png",
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


def make_client(postgres_engine: Engine, storage: FakeObjectStorage) -> TestClient:
    app = create_app(
        Settings(
            frontend_origin="http://frontend.test",
            max_upload_bytes=MAX_UPLOAD_BYTES,
        ),
        session_factory=sessionmaker(bind=postgres_engine, expire_on_commit=False),
        storage=storage,
    )
    return TestClient(app)


def test_valid_object_is_confirmed_with_postgresql_and_is_idempotent(
    postgres_engine: Engine,
    create_pending_upload: Callable[..., Upload],
) -> None:
    upload = create_pending_upload()
    storage = FakeObjectStorage(
        object_stats={upload.object_key: ObjectStat(size_bytes=512, etag="confirmed-etag")}
    )
    client = make_client(postgres_engine, storage)

    with client:
        first_response = client.post(
            f"/api/uploads/{upload.id}/confirm",
            headers={"X-User-ID": str(ALICE_ID)},
        )
        repeated_response = client.post(
            f"/api/uploads/{upload.id}/confirm",
            headers={"X-User-ID": str(ALICE_ID)},
        )

    assert first_response.status_code == 200
    assert first_response.json() == {"upload_id": str(upload.id), "status": "uploaded"}
    assert repeated_response.status_code == 200
    assert repeated_response.json() == first_response.json()
    assert storage.stat_calls == [upload.object_key]

    with Session(postgres_engine) as session:
        confirmed_upload = session.get(Upload, upload.id)

    assert confirmed_upload is not None
    assert confirmed_upload.status is UploadStatus.UPLOADED
    assert confirmed_upload.size_bytes == 512
    assert confirmed_upload.etag == "confirmed-etag"


@pytest.mark.parametrize(
    "object_stat",
    [None, ObjectStat(size_bytes=0, etag="empty"), ObjectStat(size_bytes=MAX_UPLOAD_BYTES + 1, etag="big")],
)
def test_missing_empty_or_oversized_object_cannot_be_confirmed(
    postgres_engine: Engine,
    create_pending_upload: Callable[..., Upload],
    object_stat: ObjectStat | None,
) -> None:
    upload = create_pending_upload()
    storage = FakeObjectStorage(
        object_stats={} if object_stat is None else {upload.object_key: object_stat}
    )
    client = make_client(postgres_engine, storage)

    with client:
        response = client.post(
            f"/api/uploads/{upload.id}/confirm",
            headers={"X-User-ID": str(ALICE_ID)},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "request_error", "message": "Request could not be completed"}
    }
    assert storage.stat_calls == [upload.object_key]
    with Session(postgres_engine) as session:
        pending_upload = session.get(Upload, upload.id)

    assert pending_upload is not None
    assert pending_upload.status is UploadStatus.PENDING_UPLOAD
    assert pending_upload.size_bytes is None
    assert pending_upload.etag is None


def test_foreign_and_absent_confirmation_share_a_404_without_storage_access(
    postgres_engine: Engine,
    create_pending_upload: Callable[..., Upload],
) -> None:
    hospital_a_upload = create_pending_upload(company_id=HOSPITAL_A_ID)
    storage = FakeObjectStorage(
        object_stats={
            hospital_a_upload.object_key: ObjectStat(size_bytes=512, etag="must-not-be-read")
        }
    )
    client = make_client(postgres_engine, storage)

    with client:
        foreign_response = client.post(
            f"/api/uploads/{hospital_a_upload.id}/confirm",
            headers={"X-User-ID": str(BOB_ID)},
        )
        absent_response = client.post(
            f"/api/uploads/{uuid4()}/confirm",
            headers={"X-User-ID": str(BOB_ID)},
        )

    assert foreign_response.status_code == 404
    assert foreign_response.json() == absent_response.json() == {
        "error": {"code": "not_found", "message": "Upload not found"}
    }
    assert storage.stat_calls == []
    with Session(postgres_engine) as session:
        hospital_a_upload = session.get(Upload, hospital_a_upload.id)

    assert hospital_a_upload is not None
    assert hospital_a_upload.company_id == HOSPITAL_A_ID
    assert hospital_a_upload.status is UploadStatus.PENDING_UPLOAD
