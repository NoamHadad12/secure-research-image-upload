"""Unit tests for the private MinIO adapter and startup boundary."""

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base
from app.main import create_app
from app.storage import MinioStorage


def no_bucket_policy_error() -> S3Error:
    return S3Error(
        "NoSuchBucketPolicy",
        "The bucket has no policy",
        "/research-images",
        "request-id",
        "host-id",
        None,
    )


@dataclass
class FakeMinioClient:
    bucket_is_present: bool = False
    bucket_policy: str | None = None
    made_buckets: list[tuple[str, str | None]] = field(default_factory=list)
    deleted_policies: list[str] = field(default_factory=list)

    def bucket_exists(self, bucket_name: str) -> bool:
        return self.bucket_is_present

    def make_bucket(self, bucket_name: str, location: str | None = None) -> None:
        self.bucket_is_present = True
        self.made_buckets.append((bucket_name, location))

    def get_bucket_policy(self, bucket_name: str) -> str:
        if self.bucket_policy is None:
            raise no_bucket_policy_error()
        return self.bucket_policy

    def delete_bucket_policy(self, bucket_name: str) -> None:
        self.bucket_policy = None
        self.deleted_policies.append(bucket_name)


def make_settings() -> Settings:
    return Settings(
        frontend_origin="http://frontend.test",
        minio_root_user="test-access-key",
        minio_root_password="test-secret-key",
    )


def test_storage_uses_distinct_internal_and_browser_resolvable_endpoints() -> None:
    created_clients: list[tuple[str, FakeMinioClient]] = []

    def fake_client_factory(endpoint: str, **_: object) -> FakeMinioClient:
        client = FakeMinioClient(bucket_is_present=True)
        created_clients.append((endpoint, client))
        return client

    storage = MinioStorage.from_settings(make_settings(), client_factory=fake_client_factory)

    assert [endpoint for endpoint, _ in created_clients] == ["minio:9000", "localhost:9000"]
    assert storage.internal_client is created_clients[0][1]
    assert storage.public_signing_client is created_clients[1][1]


def test_bucket_initialization_creates_once_and_removes_anonymous_policy() -> None:
    internal_client = FakeMinioClient(bucket_policy='{"Version":"2012-10-17"}')
    storage = MinioStorage(
        bucket_name="research-images",
        region="us-east-1",
        internal_client=internal_client,
        public_signing_client=FakeMinioClient(),
    )

    storage.ensure_private_bucket()
    storage.ensure_private_bucket()

    assert internal_client.made_buckets == [("research-images", "us-east-1")]
    assert internal_client.deleted_policies == ["research-images"]


@dataclass
class FakeObjectStorage:
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


def test_application_startup_accepts_a_replaceable_storage_fake(
    session_factory: sessionmaker[Session],
) -> None:
    fake_storage = FakeObjectStorage()
    app = create_app(
        Settings(frontend_origin="http://frontend.test"),
        session_factory=session_factory,
        storage=fake_storage,
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    assert fake_storage.initialization_calls == 1
