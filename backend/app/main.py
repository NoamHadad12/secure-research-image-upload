"""FastAPI application entry point and public infrastructure boundary."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.errors import error_response
from app.schemas import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API with validated configuration and safe error handlers."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.normalized_frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-User-ID"],
    )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request,
        __: RequestValidationError,
    ):
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="Request validation failed",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exception: StarletteHTTPException):
        if exception.status_code == status.HTTP_404_NOT_FOUND:
            code = "not_found"
            message = "Resource not found"
        elif exception.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            code = "method_not_allowed"
            message = "Method not allowed"
        else:
            code = "request_error"
            message = "Request could not be completed"

        return error_response(
            status_code=exception.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, __: Exception):
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred",
        )

    @app.get("/health", response_model=HealthResponse, tags=["infrastructure"])
    async def health() -> HealthResponse:
        """Report process availability without exposing dependency details."""

        return HealthResponse(status="ok")

    return app


app = create_app()
