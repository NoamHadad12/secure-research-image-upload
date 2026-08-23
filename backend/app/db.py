"""SQLAlchemy metadata shared by models and Alembic migrations."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all structured metadata tables."""
