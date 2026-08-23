"""Create companies, users, and uploads metadata tables.

Revision ID: 20260823_0001
Revises:
Create Date: 2026-08-23 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260823_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

upload_status = postgresql.ENUM(
    "pending_upload",
    "uploaded",
    "queued",
    "processing",
    "completed",
    "failed",
    name="upload_status",
    create_type=False,
)


def upgrade() -> None:
    upload_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)
    op.create_table(
        "uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", sa.String(length=128), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("status", upload_status, server_default="pending_upload", nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_uploads_company_id", "uploads", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_uploads_company_id", table_name="uploads")
    op.drop_table("uploads")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_table("users")
    op.drop_table("companies")
    upload_status.drop(op.get_bind(), checkfirst=True)
