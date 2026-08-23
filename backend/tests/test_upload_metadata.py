from uuid import UUID

import pytest
from pydantic import ValidationError

from app.upload_metadata import UploadInitiationMetadata, build_object_key


def valid_metadata(**overrides: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "sample_id": " sample-17 ",
        "filename": r"C:\incoming\Scan (1).PNG",
        "classification": " RESEARCH ",
        "content_type": "IMAGE/PNG ",
    }
    metadata.update(overrides)
    return metadata


def test_metadata_is_normalized_and_key_is_scoped_to_server_supplied_ids() -> None:
    metadata = UploadInitiationMetadata.model_validate(valid_metadata())
    company_id = UUID("00000000-0000-0000-0000-0000000000a1")
    upload_id = UUID("00000000-0000-0000-0000-000000000123")

    object_key = build_object_key(
        company_id=company_id,
        upload_id=upload_id,
        safe_filename=metadata.filename,
    )

    assert metadata.sample_id == "sample-17"
    assert metadata.classification == "research"
    assert metadata.content_type == "image/png"
    assert metadata.filename == "Scan-1.png"
    assert object_key == f"uploads/{company_id}/{upload_id}/Scan-1.png"


@pytest.mark.parametrize(
    "overrides",
    [
        {"sample_id": "   "},
        {"filename": "missing-extension"},
        {"filename": "image.png", "content_type": "image/jpeg"},
        {"classification": "top-secret"},
        {"content_type": "application/pdf"},
    ],
)
def test_invalid_required_metadata_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        UploadInitiationMetadata.model_validate(valid_metadata(**overrides))


@pytest.mark.parametrize("field_name", ["company_id", "object_key"])
def test_client_cannot_supply_tenant_or_storage_fields(field_name: str) -> None:
    with pytest.raises(ValidationError) as error:
        UploadInitiationMetadata.model_validate(valid_metadata(**{field_name: "forged"}))

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_safe_filename_is_bounded_and_cannot_be_reused_as_a_path() -> None:
    metadata = UploadInitiationMetadata.model_validate(
        valid_metadata(filename=f"{'a' * 250}.webp", content_type="image/webp")
    )

    assert metadata.filename == f"{'a' * 123}.webp"
    with pytest.raises(ValueError, match="single path segment"):
        build_object_key(
            company_id=UUID("00000000-0000-0000-0000-0000000000a1"),
            upload_id=UUID("00000000-0000-0000-0000-000000000123"),
            safe_filename="other-company/scan.png",
        )
