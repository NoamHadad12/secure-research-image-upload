"""Validation and server-generated names for upload initiation metadata."""

from __future__ import annotations

import re
import unicodedata
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

MAX_SAMPLE_ID_LENGTH: Final = 128
MAX_INPUT_FILENAME_LENGTH: Final = 255
MAX_SAFE_FILENAME_LENGTH: Final = 128

DEMO_CLASSIFICATIONS: Final = frozenset({"research", "clinical", "restricted"})
CONTENT_TYPE_EXTENSIONS: Final = {
    "image/png": frozenset({".png"}),
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/webp": frozenset({".webp"}),
}
_UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]+")


def sanitize_filename(filename: str, *, content_type: str) -> str:
    """Return a conservative basename suitable for one object-key path segment."""

    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not basename:
        raise ValueError("filename must contain a basename")

    ascii_basename = (
        unicodedata.normalize("NFKD", basename).encode("ascii", "ignore").decode("ascii")
    )
    stem, dot, suffix = ascii_basename.rpartition(".")
    if not dot:
        raise ValueError("filename must have an image extension")

    normalized_suffix = f".{suffix.lower()}"
    if normalized_suffix not in CONTENT_TYPE_EXTENSIONS[content_type]:
        raise ValueError("filename extension does not match content type")

    safe_stem = _UNSAFE_FILENAME_CHARACTERS.sub("-", stem).strip("-_.")
    if not safe_stem:
        raise ValueError("filename must contain a safe basename")

    available_stem_length = MAX_SAFE_FILENAME_LENGTH - len(normalized_suffix)
    safe_stem = safe_stem[:available_stem_length].rstrip("-_.")
    if not safe_stem:
        raise ValueError("filename must contain a safe basename")

    return f"{safe_stem}{normalized_suffix}"


def build_object_key(*, company_id: UUID, upload_id: UUID, safe_filename: str) -> str:
    """Build the only storage-key layout accepted by this application."""

    if not safe_filename or "/" in safe_filename or "\\" in safe_filename:
        raise ValueError("safe filename must be a single path segment")
    if len(safe_filename) > MAX_SAFE_FILENAME_LENGTH:
        raise ValueError("safe filename exceeds the maximum length")

    return f"uploads/{company_id}/{upload_id}/{safe_filename}"


class UploadInitiationMetadata(BaseModel):
    """Untrusted metadata accepted before a future upload-initiation route persists it."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(max_length=MAX_SAMPLE_ID_LENGTH)
    classification: str
    content_type: str
    filename: str

    @field_validator("sample_id", mode="before")
    @classmethod
    def normalize_sample_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("sample_id must not be blank")
        return normalized_value

    @field_validator("classification", mode="before")
    @classmethod
    def validate_classification(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized_value = value.strip().lower()
        if normalized_value not in DEMO_CLASSIFICATIONS:
            raise ValueError("classification is not supported")
        return normalized_value

    @field_validator("content_type", mode="before")
    @classmethod
    def validate_content_type(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized_value = value.strip().lower()
        if normalized_value not in CONTENT_TYPE_EXTENSIONS:
            raise ValueError("content_type is not an allowed image MIME type")
        return normalized_value

    @field_validator("filename", mode="after")
    @classmethod
    def normalize_filename(cls, value: str, info: ValidationInfo) -> str:
        if len(value) > MAX_INPUT_FILENAME_LENGTH:
            raise ValueError("filename exceeds the maximum length")

        content_type = info.data.get("content_type")
        if not isinstance(content_type, str):
            raise ValueError("content_type must be validated before filename")
        return sanitize_filename(value, content_type=content_type)
