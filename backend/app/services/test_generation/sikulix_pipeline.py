"""SikuliX generation pipeline — Epic 3, Story 3-13-domknięcie (AC1/AC2/AC3).

Spięcie ``PatternCropper`` w ścieżce generowania SikuliX: pobranie screenshotów z
MinIO → wycięcie bbox→PNG → zapis patternów w MinIO + odnotowanie w
``TestCode.pattern_images``. Rozwiązuje też linkage TestStep↔GUIComponent (AC2),
który w Story 3.13 był odłożony (``3-13-...md:111,197``).

Generyczny ``generate_code_for_test_cases`` pozostaje dla frameworków
selektorowych (Cypress); SikuliX ma własny pipeline, bo wymaga obrazów.
"""

import asyncio
import io
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import download_file_bytes, upload_file
from app.models.gui_screenshot import GUIAnalysisResult, GUIComponent, GUIScreenshot
from app.models.test_case import TestCase
from app.models.test_code import TestCode
from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry
from app.services.test_generation.pattern_cropper import crop_all_components

logger = logging.getLogger(__name__)


def _sanitize_label(value: Any) -> str:
    """Sanityzuj label do klucza indeksu (lower, diakrytyki/whitespace → „_")."""
    text = str(value).lower()
    text = re.sub(r"[\s-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def index_components(
    components: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Zbuduj indeksy komponentów GUI: po ``id`` oraz po sanityzowanym ``label``.

    Komponenty bez ``id`` trafiają tylko do indeksu po labelu (mogą pochodzić
    z inline stepów). Zwraca krotkę ``(by_id, by_label)``.
    """
    by_id: dict[str, dict[str, Any]] = {}
    by_label: dict[str, dict[str, Any]] = {}
    for comp in components:
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id")
        if cid:
            by_id[str(cid)] = comp
        label = comp.get("label")
        if label:
            key = _sanitize_label(label)
            if key:
                by_label.setdefault(key, comp)
    return by_id, by_label


def resolve_step_component(
    step: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_label: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Rozwiąż komponent GUI dla kroku testowego (AC2 — linkage).

    Kolejność rozdzielczości:
      1. explicit ``step.component`` z ``bbox`` → użyj jak jest (inline),
      2. ``step.component_id`` → lookup po ``id`` w indeksie DB,
      3. label-match ``step.target`` / ``step.target_element`` w indeksie DB.

    Zwraca słownik komponentu (z ``bbox`` oraz ``storage_key`` gdy z DB) lub
    ``None``, gdy powiązania nie udało się ustalić.
    """
    component = step.get("component")
    if isinstance(component, dict) and isinstance(component.get("bbox"), dict):
        return component

    comp_id = step.get("component_id")
    if comp_id:
        resolved = by_id.get(str(comp_id))
        if resolved is not None:
            return resolved

    target = step.get("target") or step.get("target_element")
    if target:
        resolved = by_label.get(_sanitize_label(target))
        if resolved is not None:
            return resolved

    return None


def _generator_component(resolved: dict[str, Any]) -> dict[str, Any]:
    """Zbuduj czysty słownik komponentu dla generatora (klucze, które czyta)."""
    return {
        "component_type": resolved.get("component_type") or resolved.get("type"),
        "label": resolved.get("label") or resolved.get("text"),
        "bbox": resolved.get("bbox"),
        "confidence": resolved.get("confidence"),
    }


async def _load_test_cases(
    db: AsyncSession,
    test_case_ids: list[uuid.UUID],
) -> list[TestCase]:
    if not test_case_ids:
        return []
    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(test_case_ids)))).scalars().all()
    return list(rows)


async def _load_gui_components(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Załaduj komponenty GUI projektu z ich ``storage_key`` screenshotu (do cropu)."""
    stmt = (
        select(GUIComponent, GUIScreenshot.storage_key)
        .join(GUIAnalysisResult, GUIComponent.analysis_id == GUIAnalysisResult.id)
        .join(GUIScreenshot, GUIAnalysisResult.screenshot_id == GUIScreenshot.id)
        .where(GUIScreenshot.project_id == project_id)
    )
    result = await db.execute(stmt)
    components: list[dict[str, Any]] = []
    for comp, storage_key in result.all():
        components.append(
            {
                "id": str(comp.id),
                "component_type": comp.component_type.value if comp.component_type else None,
                "label": comp.label,
                "bbox": comp.bbox,
                "confidence": comp.confidence,
                "storage_key": storage_key,
            }
        )
    return components


def _pattern_prefix(
    tenant_id: uuid.UUID | None,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
) -> str:
    tenant = f"{tenant_id}/" if tenant_id is not None else ""
    return f"{tenant}{project_id}/sikuli/{test_case_id}/images"


async def _crop_and_upload(
    components_by_storage: dict[str, list[dict[str, Any]]],
    bucket: str,
    dest_prefix: str,
) -> list[dict[str, Any]]:
    """Pobierz screenshoty z MinIO, wytnij patterny (bbox→PNG), wgraj je z powrotem.

    Degradacja graceful: gdy Pillow brak, ``crop_all_components`` zwraca ``[]``
    (i loguje warning) — skrypt i tak powstaje, tylko bez patternów (Task 2.3).
    """
    patterns_meta: list[dict[str, Any]] = []
    for storage_key, comps in components_by_storage.items():
        try:
            screenshot_bytes = await asyncio.to_thread(download_file_bytes, bucket, storage_key)
        except Exception as exc:  # dekoracyjne — pomijamy niedostępny screenshot
            logger.warning("SikuliX: nie pobrano screenshotu %s: %s", storage_key, exc)
            continue

        cropped = crop_all_components(screenshot_bytes, comps)
        if not cropped:
            continue

        for pattern in cropped:
            pattern_storage_key = f"{dest_prefix}/{pattern.name}"
            try:
                data = io.BytesIO(pattern.image_bytes)
                await asyncio.to_thread(
                    upload_file,
                    bucket,
                    pattern_storage_key,
                    data,
                    len(pattern.image_bytes),
                    "image/png",
                )
            except Exception as exc:  # dekoracyjne — pomijamy pojedynczy pattern
                logger.warning("SikuliX: nie zapisano patternu %s: %s", pattern.name, exc)
                continue
            patterns_meta.append(
                {
                    "name": pattern.name,
                    "storage_key": pattern_storage_key,
                    "component_id": pattern.component_id,
                }
            )
    return patterns_meta


async def generate_sikulix_code(
    db: AsyncSession,
    project_id: uuid.UUID,
    test_case_ids: list[uuid.UUID],
    tenant_id: uuid.UUID | None = None,
) -> list[TestCode]:
    """Wygeneruj skrypty SikuliX z realnymi patternami PNG (AC1/AC2/AC3).

    Dla każdego TestCase: rozwiąż linkage step→GUIComponent, wytnij patterny ze
    screenshotów (MinIO→crop→MinIO), wygeneruj skrypt przez ``SikuliXCodeGenerator``
    i utrwal ``TestCode`` z ``pattern_images``.
    """
    registry = CodeGenRegistry.get_instance()
    if not registry.is_supported("sikulix"):
        raise ValueError("Nieobslugiwany framework: sikulix")
    config = CodeGenConfig(framework="sikulix", validate_compilation=True)
    generator = registry.get_generator("sikulix", config)

    bucket = get_settings().minio_bucket_name

    test_cases = await _load_test_cases(db, test_case_ids)
    if not test_cases:
        return []

    db_components = await _load_gui_components(db, project_id)
    by_id, by_label = index_components(db_components)

    records: list[TestCode] = []
    for tc in test_cases:
        tc_dict = tc.to_dict()
        tc_dict["feature_name"] = tc.title

        croppable_by_storage: dict[str, list[dict[str, Any]]] = {}
        raw_steps = tc_dict.get("steps")
        if isinstance(raw_steps, list):
            enriched_steps: list[dict[str, Any]] = []
            for step in raw_steps:
                if isinstance(step, dict):
                    resolved = resolve_step_component(step, by_id, by_label)
                    if resolved is not None:
                        step = {**step, "component": _generator_component(resolved)}
                        storage_key = resolved.get("storage_key")
                        bbox = resolved.get("bbox")
                        if storage_key and isinstance(bbox, dict):
                            croppable_by_storage.setdefault(storage_key, []).append(resolved)
                enriched_steps.append(step)
            tc_dict["steps"] = enriched_steps

        dest_prefix = _pattern_prefix(tenant_id, project_id, tc.id)
        pattern_images = await _crop_and_upload(croppable_by_storage, bucket, dest_prefix)

        test_file = generator.generate_test_file([tc_dict], config)
        record = TestCode(
            test_case_id=tc.id,
            framework=test_file.framework,
            language=test_file.language,
            code=test_file.content,
            file_path=test_file.file_path,
            pattern_images=pattern_images or None,
        )
        if tenant_id is not None:
            record.tenant_id = tenant_id
        db.add(record)
        records.append(record)

    await db.flush()
    return records
