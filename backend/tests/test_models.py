from app.db import Base
from app.models import UploadStatus


def test_upload_status_contains_the_full_required_lifecycle() -> None:
    assert [status.value for status in UploadStatus] == [
        "pending_upload",
        "uploaded",
        "queued",
        "processing",
        "completed",
        "failed",
    ]


def test_upload_metadata_schema_enforces_company_index_and_unique_object_key() -> None:
    uploads = Base.metadata.tables["uploads"]

    assert any(index.columns.keys() == ["company_id"] for index in uploads.indexes)
    assert uploads.c.object_key.unique is True
    assert uploads.c.status.default.arg is UploadStatus.PENDING_UPLOAD
    assert str(uploads.c.status.server_default.arg) == "pending_upload"


def test_models_match_the_expected_company_relationships() -> None:
    companies = Base.metadata.tables["companies"]
    users = Base.metadata.tables["users"]
    uploads = Base.metadata.tables["uploads"]

    assert companies.c.name.unique is True
    assert {foreign_key.target_fullname for foreign_key in users.c.company_id.foreign_keys} == {
        "companies.id"
    }
    assert {foreign_key.target_fullname for foreign_key in uploads.c.company_id.foreign_keys} == {
        "companies.id"
    }
