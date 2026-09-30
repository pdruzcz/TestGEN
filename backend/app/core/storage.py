"""MinIO/S3 client wrapper.

The MinIO Python SDK is synchronous — call these helpers from sync contexts
(Celery workers) directly, or from FastAPI async endpoints through
``asyncio.to_thread()``.
"""

import logging
from typing import BinaryIO

from minio import Minio

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    """Return a cached MinIO client built from current settings."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_use_ssl,
        )
    return _client


def reset_minio_client() -> None:
    """Reset the cached client (tests only)."""
    global _client
    _client = None


def ensure_bucket_exists(bucket_name: str) -> None:
    """Create the bucket if it does not already exist."""
    client = get_minio_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        logger.info("Created MinIO bucket %s", bucket_name)


def upload_file(
    bucket: str,
    object_name: str,
    data: BinaryIO,
    length: int,
    content_type: str | None = None,
) -> None:
    """Upload a file-like object to MinIO."""
    client = get_minio_client()
    client.put_object(
        bucket,
        object_name,
        data,
        length,
        content_type=content_type or "application/octet-stream",
    )


def download_file_bytes(bucket: str, object_name: str) -> bytes:
    """Download a file from MinIO and return its raw bytes."""
    client = get_minio_client()
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(bucket: str, object_name: str) -> None:
    """Remove a single object. Safe to call on missing keys."""
    client = get_minio_client()
    client.remove_object(bucket, object_name)
