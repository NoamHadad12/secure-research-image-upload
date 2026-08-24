"""Development identities and the server-side tenant-resolution dependency."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db_session
from app.models import Company, User

HOSPITAL_A_ID = UUID("00000000-0000-0000-0000-0000000000a1")
HOSPITAL_B_ID = UUID("00000000-0000-0000-0000-0000000000b1")
DANA_ID = UUID("00000000-0000-0000-0000-0000000000a2")
DAVID_ID = UUID("00000000-0000-0000-0000-0000000000b2")


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated development user and tenant resolved by the backend."""

    user_id: UUID
    display_name: str
    company_id: UUID
    company_name: str


def _ensure_company(session: Session, *, company_id: UUID, name: str) -> None:
    existing_by_id = session.get(Company, company_id)
    existing_by_name = session.scalar(select(Company).where(Company.name == name))

    if existing_by_id is not None and existing_by_id.name != name:
        raise RuntimeError("Development company ID is already assigned to another company")
    if existing_by_name is not None and existing_by_name.id != company_id:
        raise RuntimeError("Development company name is already assigned to another company")
    if existing_by_id is None:
        session.add(Company(id=company_id, name=name))


def _ensure_user(
    session: Session,
    *,
    user_id: UUID,
    display_name: str,
    company_id: UUID,
) -> None:
    existing = session.get(User, user_id)
    if existing is None:
        session.add(
            User(
                id=user_id,
                display_name=display_name,
                company_id=company_id,
            )
        )
        return

    if existing.company_id != company_id:
        raise RuntimeError("Development user ID is already assigned to a different identity")

    # Display names are presentation data. Keep the stable seeded ID and company
    # ownership while allowing an existing local database to adopt a renamed demo user.
    if existing.display_name != display_name:
        existing.display_name = display_name


def seed_development_identities(session: Session) -> None:
    """Ensure the fixed Hospital A/B development identities exist without duplicates."""

    _ensure_company(session, company_id=HOSPITAL_A_ID, name="Hospital A")
    _ensure_company(session, company_id=HOSPITAL_B_ID, name="Hospital B")
    session.flush()

    _ensure_user(
        session,
        user_id=DANA_ID,
        display_name="Dana",
        company_id=HOSPITAL_A_ID,
    )
    _ensure_user(
        session,
        user_id=DAVID_ID,
        display_name="David",
        company_id=HOSPITAL_B_ID,
    )
    session.flush()


def _reject_unrecognized_development_user() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Development user is not recognized",
    )


def get_current_user(
    x_user_id: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_db_session),
) -> CurrentUser:
    """Resolve `X-User-ID` to a tenant; no client company value is consulted."""

    if not x_user_id:
        _reject_unrecognized_development_user()

    try:
        user_id = UUID(x_user_id)
    except ValueError:
        _reject_unrecognized_development_user()

    user = session.scalar(
        select(User).options(joinedload(User.company)).where(User.id == user_id)
    )
    if user is None:
        _reject_unrecognized_development_user()

    return CurrentUser(
        user_id=user.id,
        display_name=user.display_name,
        company_id=user.company.id,
        company_name=user.company.name,
    )
