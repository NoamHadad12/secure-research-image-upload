"""Safe, consistent error responses for the public API boundary."""

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    """Return a deliberately small response that contains no internal details."""

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorBody(code=code, message=message)).model_dump(),
    )
