from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.identity import HOSPITAL_A_ID, HOSPITAL_B_ID, seed_development_identities
from app.models import Upload
from app.upload_repository import add_upload, get_upload_for_company, list_uploads_for_company


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


def make_upload(*, company_id: UUID, filename: str) -> Upload:
    """Build metadata only; upload-byte validation belongs to later stories."""

    upload_id = uuid4()
    return Upload(
        id=upload_id,
        sample_id=f"sample-{filename}",
        original_filename=filename,
        classification="research",
        company_id=company_id,
        object_key=f"test/{company_id}/{upload_id}/{filename}",
        content_type="image/png",
    )


def seed_uploads(session_factory: sessionmaker[Session]) -> tuple[Upload, Upload]:
    with session_factory() as session:
        seed_development_identities(session)
        hospital_a_upload = make_upload(company_id=HOSPITAL_A_ID, filename="a.png")
        hospital_b_upload = make_upload(company_id=HOSPITAL_B_ID, filename="b.png")
        session.add_all([hospital_a_upload, hospital_b_upload])
        session.commit()

    return hospital_a_upload, hospital_b_upload


def test_add_upload_flushes_metadata_without_committing(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        seed_development_identities(session)
        upload = make_upload(company_id=HOSPITAL_A_ID, filename="new.png")

        persisted = add_upload(session, upload=upload)

        assert persisted is upload
        assert session.get(Upload, upload.id) is upload
        session.rollback()


def test_list_uploads_returns_only_the_requested_company_records(
    session_factory: sessionmaker[Session],
) -> None:
    hospital_a_upload, hospital_b_upload = seed_uploads(session_factory)

    with session_factory() as session:
        hospital_a_uploads = list_uploads_for_company(session, company_id=HOSPITAL_A_ID)
        hospital_b_uploads = list_uploads_for_company(session, company_id=HOSPITAL_B_ID)

    assert [upload.id for upload in hospital_a_uploads] == [hospital_a_upload.id]
    assert [upload.id for upload in hospital_b_uploads] == [hospital_b_upload.id]


def test_foreign_and_absent_upload_ids_share_the_same_not_found_outcome(
    session_factory: sessionmaker[Session],
) -> None:
    hospital_a_upload, _ = seed_uploads(session_factory)

    with session_factory() as session:
        foreign_result = get_upload_for_company(
            session,
            upload_id=hospital_a_upload.id,
            company_id=HOSPITAL_B_ID,
        )
        absent_result = get_upload_for_company(
            session,
            upload_id=uuid4(),
            company_id=HOSPITAL_B_ID,
        )

    assert foreign_result is None
    assert absent_result is None


def test_owner_can_resolve_its_own_upload(
    session_factory: sessionmaker[Session],
) -> None:
    hospital_a_upload, _ = seed_uploads(session_factory)

    with session_factory() as session:
        result = get_upload_for_company(
            session,
            upload_id=hospital_a_upload.id,
            company_id=HOSPITAL_A_ID,
        )

    assert result is not None
    assert result.id == hospital_a_upload.id
    assert result.company_id == HOSPITAL_A_ID
