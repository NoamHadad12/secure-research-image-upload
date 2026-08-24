from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base
from app.identity import (
    DANA_ID,
    DAVID_ID,
    HOSPITAL_A_ID,
    HOSPITAL_B_ID,
    CurrentUser,
    get_current_user,
    seed_development_identities,
)
from app.main import create_app
from app.models import Company, User


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


def test_seed_is_idempotent_and_creates_the_fixed_hospital_users(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        seed_development_identities(session)
        session.commit()

    with session_factory() as session:
        seed_development_identities(session)
        session.commit()

        assert session.scalar(select(func.count()).select_from(Company)) == 2
        assert session.scalar(select(func.count()).select_from(User)) == 2
        assert session.get(Company, HOSPITAL_A_ID).name == "Hospital A"
        assert session.get(Company, HOSPITAL_B_ID).name == "Hospital B"
        assert session.get(User, DANA_ID).display_name == "Dana"
        assert session.get(User, DAVID_ID).display_name == "David"


def test_seed_updates_legacy_display_names_without_changing_ownership(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Company(id=HOSPITAL_A_ID, name="Hospital A"),
                Company(id=HOSPITAL_B_ID, name="Hospital B"),
            ]
        )
        session.flush()
        session.add_all(
            [
                User(id=DANA_ID, display_name="Alice", company_id=HOSPITAL_A_ID),
                User(id=DAVID_ID, display_name="Bob", company_id=HOSPITAL_B_ID),
            ]
        )
        session.commit()

    with session_factory() as session:
        seed_development_identities(session)
        session.commit()

        assert session.scalar(select(func.count()).select_from(User)) == 2
        assert session.get(User, DANA_ID).display_name == "Dana"
        assert session.get(User, DANA_ID).company_id == HOSPITAL_A_ID
        assert session.get(User, DAVID_ID).display_name == "David"
        assert session.get(User, DAVID_ID).company_id == HOSPITAL_B_ID


def _make_identity_client(session_factory: sessionmaker[Session]) -> TestClient:
    app = create_app(
        Settings(frontend_origin="http://frontend.test"),
        session_factory=session_factory,
    )

    @app.get("/test/whoami")
    def whoami(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {
            "user_id": str(current_user.user_id),
            "company_id": str(current_user.company_id),
            "company_name": current_user.company_name,
        }

    return TestClient(app)


def test_header_resolves_company_only_from_the_seeded_user(
    session_factory: sessionmaker[Session],
) -> None:
    client = _make_identity_client(session_factory)

    with client:
        response = client.get(
            "/test/whoami",
            headers={
                "X-User-ID": str(DANA_ID),
                "X-Company-ID": str(HOSPITAL_B_ID),
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(DANA_ID),
        "company_id": str(HOSPITAL_A_ID),
        "company_name": "Hospital A",
    }


@pytest.mark.parametrize("header_value", [None, "not-a-uuid", str(uuid4())])
def test_missing_or_unknown_development_users_are_rejected(
    session_factory: sessionmaker[Session],
    header_value: str | None,
) -> None:
    client = _make_identity_client(session_factory)
    headers = {} if header_value is None else {"X-User-ID": header_value}

    with client:
        response = client.get("/test/whoami", headers=headers)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "request_error",
            "message": "Request could not be completed",
        }
    }
