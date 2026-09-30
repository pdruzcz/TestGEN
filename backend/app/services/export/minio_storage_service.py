"""Przechowywanie eksportów w MinIO — Story 6.7, AC7.

Bucket ``testgen-exports`` z polityką lifecycle 7 dni (automatyczne
wygasanie plików). SDK MinIO jest synchroniczne — z endpointów async wołać
przez ``asyncio.to_thread()``.
"""

import io
import logging

from app.core import storage

logger = logging.getLogger(__name__)

EXPORTS_BUCKET = "testgen-exports"
EXPORT_TTL_DAYS = 7

_lifecycle_applied = False


def ensure_exports_bucket() -> None:
    """Tworzy bucket eksportów i ustawia 7-dniową politykę wygasania."""
    global _lifecycle_applied
    storage.ensure_bucket_exists(EXPORTS_BUCKET)
    if _lifecycle_applied:
        return
    try:
        from minio.commonconfig import ENABLED, Filter
        from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

        config = LifecycleConfig(
            [
                Rule(
                    ENABLED,
                    rule_filter=Filter(prefix=""),
                    rule_id="testgen-exports-ttl",
                    expiration=Expiration(days=EXPORT_TTL_DAYS),
                )
            ]
        )
        storage.get_minio_client().set_bucket_lifecycle(EXPORTS_BUCKET, config)
        _lifecycle_applied = True
    except Exception:  # pragma: no cover — brak uprawnień/wsparcia lifecycle
        logger.warning(
            "Nie udało się ustawić polityki lifecycle na buckecie %s — pliki nie wygasną automatycznie",
            EXPORTS_BUCKET,
        )


def upload_export(object_name: str, data: bytes, content_type: str) -> None:
    """Zapisuje wygenerowany plik eksportu do MinIO."""
    ensure_exports_bucket()
    storage.upload_file(EXPORTS_BUCKET, object_name, io.BytesIO(data), len(data), content_type)


def download_export(object_name: str) -> bytes:
    """Pobiera bajty pliku eksportu z MinIO."""
    return storage.download_file_bytes(EXPORTS_BUCKET, object_name)
