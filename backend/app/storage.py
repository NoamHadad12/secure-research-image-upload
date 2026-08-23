"""Private MinIO storage boundary used by the backend only."""

from collections.abc import Callable
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from app.config import Settings


class ObjectStorage(Protocol):
    """Minimum storage behavior needed during application startup."""

    def ensure_private_bucket(self) -> None:
        """Create the configured bucket when needed and ensure it has no public policy."""


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


MinioClientFactory = Callable[..., MinioBucketClient]


class MinioStorage:
    """MinIO adapter with separate internal and browser-facing signing clients."""

    def __init__(
        self,
        *,
        bucket_name: str,
        region: str,
        internal_client: MinioBucketClient,
        public_signing_client: MinioBucketClient,
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
