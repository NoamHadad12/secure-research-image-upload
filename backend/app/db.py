"""Database infrastructure shared by API dependencies and Alembic migrations."""

from collections.abc import Generator
from typing import TypeAlias

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


SessionFactory: TypeAlias = sessionmaker[Session]


class Base(DeclarativeBase):
    """Base class for all structured metadata tables."""


def create_session_factory(database_url: str) -> tuple[Engine, SessionFactory]:
    """Create a synchronous PostgreSQL engine and its request-session factory."""

    engine = create_engine(database_url, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def get_db_session(request: Request) -> Generator[Session, None, None]:
    """Yield one database session for a request and always close it afterwards."""

    session_factory: SessionFactory | None = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("Database session factory is not configured")

    with session_factory() as session:
        yield session
