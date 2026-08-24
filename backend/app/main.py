"""FastAPI application entry point and public infrastructure boundary."""

from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.db import SessionFactory, create_session_factory, get_db_session
from app.errors import error_response
from app.identity import CurrentUser, get_current_user, seed_development_identities
from app.models import Upload, UploadStatus
from app.processing import process_confirmed_upload
from app.schemas import (
    HealthResponse,
    UploadConfirmationResponse,
    UploadInitiationResponse,
    UploadRecordResponse,
)
from app.storage import MinioStorage, ObjectMissingError, ObjectStorage
from app.upload_metadata import UploadInitiationMetadata, build_object_key
from app.upload_repository import add_upload, get_upload_for_company, list_uploads_for_company

PRESIGNED_UPLOAD_URL_EXPIRY = timedelta(minutes=5)


def get_object_storage(request: Request) -> ObjectStorage:
    """Return the application storage adapter without exposing its credentials."""

    storage: ObjectStorage | None = getattr(request.app.state, "storage", None)
    if storage is None:
        raise RuntimeError("Object storage is not configured")
    return storage


@asynccontextmanager
async def application_lifespan(app: FastAPI):
    """Seed development users after migrations have made the schema available."""

    session_factory: SessionFactory | None = app.state.session_factory
    if session_factory is None:
        raise RuntimeError("DATABASE_URL must be configured before starting the API")

    storage: ObjectStorage | None = app.state.storage
    if storage is not None:
        storage.ensure_private_bucket()

    with session_factory() as session:
        try:
            seed_development_identities(session)
            session.commit()
        except Exception:
            session.rollback()
            raise

    try:
        yield
    finally:
        database_engine = getattr(app.state, "database_engine", None)
        if database_engine is not None:
            database_engine.dispose()


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: SessionFactory | None = None,
    storage: ObjectStorage | None = None,
) -> FastAPI:
    """Create the API with validated configuration and safe error handlers."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=application_lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database_engine = None
    app.state.session_factory = session_factory
    app.state.storage = storage
    if session_factory is None and resolved_settings.database_url:
        database_engine, configured_session_factory = create_session_factory(
            resolved_settings.required_database_url
        )
        app.state.database_engine = database_engine
        app.state.session_factory = configured_session_factory
        if storage is None:
            app.state.storage = MinioStorage.from_settings(resolved_settings)

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
            message = (
                "Upload not found"
                if exception.detail == "Upload not found"
                else "Resource not found"
            )
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

    @app.post(
        "/api/uploads/initiate",
        response_model=UploadInitiationResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["uploads"],
    )
    def initiate_upload(
        metadata: UploadInitiationMetadata,
        current_user: CurrentUser = Depends(get_current_user),
        session: Session = Depends(get_db_session),
        storage: ObjectStorage = Depends(get_object_storage),
    ) -> UploadInitiationResponse:
        """Persist a tenant-owned pending upload before issuing its temporary PUT URL."""

        upload_id = uuid4()
        object_key = build_object_key(
            company_id=current_user.company_id,
            upload_id=upload_id,
            safe_filename=metadata.filename,
        )
        upload = Upload(
            id=upload_id,
            sample_id=metadata.sample_id,
            original_filename=metadata.filename,
            classification=metadata.classification,
            company_id=current_user.company_id,
            object_key=object_key,
            content_type=metadata.content_type,
        )

        try:
            add_upload(session, upload=upload)
            upload_url = storage.presigned_put_url(
                object_key=upload.object_key,
                expires=PRESIGNED_UPLOAD_URL_EXPIRY,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise

        return UploadInitiationResponse(
            upload_id=upload.id,
            upload_url=upload_url,
            upload_url_expires_in_seconds=int(PRESIGNED_UPLOAD_URL_EXPIRY.total_seconds()),
        )

    @app.post(
        "/api/uploads/{upload_id}/confirm",
        response_model=UploadConfirmationResponse,
        tags=["uploads"],
    )
    def confirm_upload(
        upload_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: CurrentUser = Depends(get_current_user),
        session: Session = Depends(get_db_session),
        storage: ObjectStorage = Depends(get_object_storage),
    ) -> UploadConfirmationResponse:
        """Verify an authorized MinIO object before recording it as uploaded."""

        upload = get_upload_for_company(
            session,
            upload_id=upload_id,
            company_id=current_user.company_id,
        )
        if upload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

        if upload.status in {
            UploadStatus.UPLOADED,
            UploadStatus.QUEUED,
            UploadStatus.PROCESSING,
            UploadStatus.COMPLETED,
        }:
            return UploadConfirmationResponse(upload_id=upload.id, status=upload.status.value)
        if upload.status is not UploadStatus.PENDING_UPLOAD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload cannot be confirmed",
            )

        try:
            object_stat = storage.stat_object(object_key=upload.object_key)
        except ObjectMissingError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload cannot be confirmed",
            ) from None

        if object_stat.size_bytes <= 0 or object_stat.size_bytes > resolved_settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload cannot be confirmed",
            )

        try:
            upload.size_bytes = object_stat.size_bytes
            upload.etag = object_stat.etag
            upload.status = UploadStatus.UPLOADED
            session.commit()
        except Exception:
            session.rollback()
            raise

        session_factory: SessionFactory | None = app.state.session_factory
        if session_factory is None:
            raise RuntimeError("Database session factory is not configured")
        background_tasks.add_task(process_confirmed_upload, session_factory, upload.id)

        return UploadConfirmationResponse(upload_id=upload.id, status=upload.status.value)

    @app.get(
        "/api/uploads",
        response_model=list[UploadRecordResponse],
        tags=["uploads"],
    )
    def list_uploads(
        current_user: CurrentUser = Depends(get_current_user),
        session: Session = Depends(get_db_session),
    ) -> list[UploadRecordResponse]:
        """List only metadata records owned by the current user's company."""

        return [
            UploadRecordResponse(
                upload_id=upload.id,
                sample_id=upload.sample_id,
                filename=upload.original_filename,
                classification=upload.classification,
                status=upload.status.value,
                created_at=upload.created_at,
            )
            for upload in list_uploads_for_company(session, company_id=current_user.company_id)
        ]

    @app.get(
        "/api/uploads/{upload_id}",
        response_model=UploadRecordResponse,
        tags=["uploads"],
    )
    def get_upload(
        upload_id: UUID,
        current_user: CurrentUser = Depends(get_current_user),
        session: Session = Depends(get_db_session),
    ) -> UploadRecordResponse:
        """Return an owned record or the generic not-found response."""

        upload = get_upload_for_company(
            session,
            upload_id=upload_id,
            company_id=current_user.company_id,
        )
        if upload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

        return UploadRecordResponse(
            upload_id=upload.id,
            sample_id=upload.sample_id,
            filename=upload.original_filename,
            classification=upload.classification,
            status=upload.status.value,
            created_at=upload.created_at,
        )

    return app


app = create_app()
