"""Eksport raportów — Story 6.7 (FR45).

POST /projects/:id/reports/export — asynchroniczne generowanie pliku
(BackgroundTasks) w formacie PDF/HTML/CSV/XLSX/JSON/YAML, zapis do MinIO
(bucket ``testgen-exports``, 7 dni — AC7). Status śledzony w Redis
(TTL 7 dni), pobranie przez GET /exports/:id/download z nagłówkiem
Content-Disposition (AC8).
"""

import asyncio
import io
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.dependencies import get_current_user, get_redis, get_tenant
from app.core.exceptions import NotFoundError
from app.core.redis import get_redis as get_redis_client
from app.models.user import User
from app.schemas.report_export import (
    ExportStatusResponse,
    ReportExportRequest,
    ReportExportResponse,
)
from app.services.export import (
    csv_export_service,
    excel_export_service,
    html_export_service,
    json_export_service,
    minio_storage_service,
    pdf_export_service,
    yaml_export_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["report-exports"])

_RENDERERS = {
    "pdf": pdf_export_service.render,
    "html": html_export_service.render,
    "csv": csv_export_service.render,
    "xlsx": excel_export_service.render,
    "json": json_export_service.render,
    "yaml": yaml_export_service.render,
}

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "html": "text/html; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
    "yaml": "application/yaml",
}

EXTENSIONS = {
    "pdf": "pdf",
    "html": "html",
    "csv": "csv",
    "xlsx": "xlsx",
    "json": "json",
    "yaml": "yaml",
}

_REDIS_PREFIX = "report_export:"
_RECORD_TTL_SECONDS = minio_storage_service.EXPORT_TTL_DAYS * 24 * 3600


def _redis_key(export_id: uuid.UUID | str) -> str:
    return f"{_REDIS_PREFIX}{export_id}"


async def _load_record(redis: Redis, export_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
    raw = await redis.get(_redis_key(export_id))
    if not raw:
        raise NotFoundError("Nie znaleziono eksportu (mógł wygasnąć po 7 dniach)")
    record = json.loads(raw)
    if record.get("tenant_id") != str(tenant_id):
        raise NotFoundError("Nie znaleziono eksportu (mógł wygasnąć po 7 dniach)")
    return record


async def _run_export(export_id: str, report_type: str, report: dict, record: dict) -> None:
    """Zadanie w tle: render → upload do MinIO → aktualizacja statusu w Redis."""
    redis = await get_redis_client()
    try:
        renderer = _RENDERERS[record["format"]]
        data = await asyncio.to_thread(renderer, report, report_type)
        await asyncio.to_thread(
            minio_storage_service.upload_export,
            record["object_name"],
            data,
            record["content_type"],
        )
        record["status"] = "done"
    except Exception:
        logger.exception("Eksport raportu %s (%s) nie powiódł się", export_id, record.get("format"))
        record["status"] = "error"
        record["error"] = "Nie udało się wygenerować pliku eksportu."
    await redis.set(_redis_key(export_id), json.dumps(record), ex=_RECORD_TTL_SECONDS)

    if record["status"] == "done":
        await _emit_export_ready(export_id, record)


async def _emit_export_ready(export_id: str, record: dict) -> None:
    """Webhook ``export.ready`` po udanym wygenerowaniu pliku (Story 8.7, AC2).

    ``download_url`` wskazuje na endpoint TestGEN, nie na MinIO: link do
    magazynu wygasa i omija kontrolę dostępu, a ten sprawdza tenanta.
    """
    try:
        from app.core.config import get_settings
        from app.services.integrations.event_emitter import emit_event_standalone

        base = get_settings().api_public_base_url.rstrip("/")
        await emit_event_standalone(
            "export.ready",
            uuid.UUID(record["tenant_id"]),
            {
                "export_id": export_id,
                "project_id": record.get("project_id"),
                "format": record.get("format"),
                "filename": record.get("filename"),
                "download_url": f"{base}/api/v1/exports/{export_id}/download",
            },
        )
    except Exception:
        logger.warning("Nie udało się wyemitować export.ready", exc_info=True)


@router.post(
    "/projects/{project_id}/reports/export",
    status_code=202,
    response_model=ReportExportResponse,
)
async def request_report_export(
    project_id: uuid.UUID,
    payload: ReportExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    redis: Redis = Depends(get_redis),
) -> ReportExportResponse:
    """Rozpoczyna asynchroniczne generowanie pliku eksportu (AC1-AC7)."""
    export_id = str(uuid.uuid4())
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"raport_{project_id}_{timestamp}.{EXTENSIONS[payload.format]}"
    record = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "format": payload.format,
        "status": "pending",
        "filename": filename,
        "object_name": f"{tenant_id}/{export_id}/{filename}",
        "content_type": CONTENT_TYPES[payload.format],
        "error": None,
    }
    await redis.set(_redis_key(export_id), json.dumps(record), ex=_RECORD_TTL_SECONDS)
    background_tasks.add_task(
        _run_export,
        export_id,
        payload.report_type,
        payload.report.model_dump(mode="json"),
        record,
    )
    return ReportExportResponse(export_id=export_id, status="pending")


@router.get("/exports/{export_id}/status", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    redis: Redis = Depends(get_redis),
) -> ExportStatusResponse:
    """Status generowania eksportu — polling z FE (AC1/AC7)."""
    record = await _load_record(redis, export_id, tenant_id)
    return ExportStatusResponse(
        export_id=str(export_id),
        status=record["status"],
        export_format=record["format"],
        filename=record["filename"],
        error=record.get("error"),
    )


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    """Pobranie gotowego pliku z Content-Disposition (AC8)."""
    record = await _load_record(redis, export_id, tenant_id)
    if record["status"] != "done":
        raise NotFoundError("Plik eksportu nie jest jeszcze gotowy")
    data = await asyncio.to_thread(minio_storage_service.download_export, record["object_name"])
    return StreamingResponse(
        io.BytesIO(data),
        media_type=record["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{record["filename"]}"'},
    )
