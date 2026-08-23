"""Regression coverage for PostgreSQL-specific metadata behavior."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.identity import HOSPITAL_A_ID, seed_development_identities
from app.models import Upload, UploadStatus


@pytest.fixture(scope="module")
def postgres_engine() -> Iterator[Engine]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL enum regression coverage")

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


def test_upload_status_uses_lowercase_postgresql_enum_values(
    postgres_engine: Engine,
) -> None:
    """A pending upload persists the PostgreSQL enum value, not its Python name."""

    with Session(postgres_engine) as session:
        seed_development_identities(session)
        session.commit()

    with Session(postgres_engine) as session:
        upload = Upload(
            sample_id="enum-regression",
            original_filename="enum-regression.png",
            classification="research",
            company_id=HOSPITAL_A_ID,
            object_key=f"regression/{uuid4()}",
            content_type="image/png",
        )
        session.add(upload)
        session.flush()

        stored_status = session.execute(
            text("SELECT status::text FROM uploads WHERE id = :upload_id"),
            {"upload_id": upload.id},
        ).scalar_one()

        assert upload.status is UploadStatus.PENDING_UPLOAD
        assert stored_status == UploadStatus.PENDING_UPLOAD.value

        session.rollback()
