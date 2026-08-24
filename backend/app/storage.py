"""Private MinIO storage boundary used by the backend only."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from app.config import Settings


class ObjectStorage(Protocol):
    """Backend-only storage behavior needed by startup and upload initiation."""

    def ensure_private_bucket(self) -> None:
        """Create the configured bucket when needed and ensure it has no public policy."""

    def presigned_put_url(self, *, object_key: str, expires: timedelta) -> str:
        """Create a short-lived browser-reachable URL for one object PUT."""

    def presigned_get_url(self, *, object_key: str, expires: timedelta) -> str:
        """Create a short-lived browser-reachable URL for one authorized object GET."""

    def stat_object(self, *, object_key: str) -> "ObjectStat":
        """Read trusted object size and ETag after application authorization."""


@dataclass(frozen=True)
class ObjectStat:
    """Object metadata required to confirm a direct browser upload."""

    size_bytes: int
    etag: str


class ObjectMissingError(Exception):
    """The authorized object is not present in MinIO yet."""


class MinioBucketClient(Protocol):
    """Subset of the MinIO client used for private-bucket initialization."""

    def bucket_exists(self, bucket_name: str) -> bool:
        """Return whether a bucket exists."""

    def make_bucket(self, bucket_name: str, location: str | None = None) -> None:
        """Create a bucket in the configured region."""

    def get_bucket_policy(self, bucket_name: str) -> str:
        """Return a bucket policy or raise when no policy exists."""

    def delete_bucket_policy(self, bucket_name: str) -> None:
        """Remove a bucket policy."""


class MinioSigningClient(MinioBucketClient, Protocol):
    """Subset of the public MinIO client used to sign browser object requests."""

    def presigned_put_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta,
    ) -> str:
        """Create a presigned PUT URL for an object in a private bucket."""

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta,
    ) -> str:
        """Create a presigned GET URL for an object in a private bucket."""


class MinioObjectStatClient(MinioBucketClient, Protocol):
    """Subset of the internal MinIO client used to stat one object."""

    def stat_object(self, bucket_name: str, object_name: str) -> object:
        """Return MinIO object metadata or raise an S3 error."""


MinioClientFactory = Callable[..., MinioBucketClient]


class MinioStorage:
    """MinIO adapter with separate internal and browser-facing signing clients."""

    def __init__(
        self,
        *,
        bucket_name: str,
        region: str,
        internal_client: MinioObjectStatClient,
        public_signing_client: MinioSigningClient,
    ) -> None:
        self.bucket_name = bucket_name
        self.region = region
        self.internal_client = internal_client
        self.public_signing_client = public_signing_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        client_factory: MinioClientFactory = Minio,
    ) -> "MinioStorage":
        """Build separate SDK clients without exposing credentials outside the backend."""

        if settings.minio_root_user is None or settings.minio_root_password is None:
            raise RuntimeError("MINIO_ROOT_USER and MINIO_ROOT_PASSWORD must be configured")

        client_arguments = {
            "access_key": settings.minio_root_user,
            "secret_key": settings.minio_root_password.get_secret_value(),
            "secure": False,
            "region": settings.minio_region,
        }
        return cls(
            bucket_name=settings.minio_bucket,
            region=settings.minio_region,
            internal_client=client_factory(
                settings.minio_internal_endpoint,
                **client_arguments,
            ),
            public_signing_client=client_factory(
                settings.minio_public_endpoint,
                **client_arguments,
            ),
        )

    def ensure_private_bucket(self) -> None:
        """Idempotently create the bucket and remove every anonymous bucket policy."""

        if not self.internal_client.bucket_exists(self.bucket_name):
            try:
                self.internal_client.make_bucket(self.bucket_name, location=self.region)
            except S3Error as error:
                if error.code != "BucketAlreadyOwnedByYou":
                    raise

        try:
            self.internal_client.get_bucket_policy(self.bucket_name)
        except S3Error as error:
            if error.code != "NoSuchBucketPolicy":
                raise
        else:
            self.internal_client.delete_bucket_policy(self.bucket_name)

    def presigned_put_url(self, *, object_key: str, expires: timedelta) -> str:
        """Sign a PUT against the browser-reachable MinIO endpoint without rewriting it."""

        return self.public_signing_client.presigned_put_object(
            self.bucket_name,
            object_key,
            expires=expires,
        )

    def presigned_get_url(self, *, object_key: str, expires: timedelta) -> str:
        """Sign a GET against the browser-reachable MinIO endpoint without rewriting it."""

        return self.public_signing_client.presigned_get_object(
            self.bucket_name,
            object_key,
            expires=expires,
        )

    def stat_object(self, *, object_key: str) -> ObjectStat:
        """Read object metadata through the Docker-internal MinIO endpoint."""

        try:
            result = self.internal_client.stat_object(self.bucket_name, object_key)
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject"}:
                raise ObjectMissingError from error
            raise

        size_bytes = getattr(result, "size", None)
        etag = getattr(result, "etag", None)
        if not isinstance(size_bytes, int) or not isinstance(etag, str):
            raise RuntimeError("MinIO returned incomplete object metadata")
        return ObjectStat(size_bytes=size_bytes, etag=etag)
