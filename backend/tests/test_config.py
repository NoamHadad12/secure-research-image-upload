import pytest
from pydantic import ValidationError

from app.config import Settings


def test_frontend_origin_is_normalized() -> None:
    settings = Settings(frontend_origin="http://frontend.test/")

    assert settings.normalized_frontend_origin == "http://frontend.test"


@pytest.mark.parametrize(
    "origin",
    ["not-a-url", "http://frontend.test/records", "ftp://frontend.test"],
)
def test_invalid_frontend_origin_is_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(frontend_origin=origin)
