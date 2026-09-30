"""Konfiguracja platformy — odczyt i zapis globalnych ustawień (Story 6.15, AC7).

Konfiguracja jest podzielona na sekcje przechowywane po jednym wierszu w tabeli
``platform_settings``.  Braki uzupełniane są wartościami domyślnymi ze schematów
Pydantic, dzięki czemu nowa sekcja lub nowe pole nie wymaga migracji danych.
"""

import uuid
from typing import Any

import pydantic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.exceptions import ValidationError
from app.models.platform_setting import PlatformSetting
from app.models.user import User
from app.schemas.admin import (
    DEFAULT_FEATURE_FLAGS,
    LimitsConfig,
    LlmConfig,
    MaintenanceConfig,
)
from app.services.admin.audit_service import log_action

CONFIG_SECTIONS = ("limits", "llm", "maintenance", "feature_flags")

_SECTION_MODELS: dict[str, type[pydantic.BaseModel]] = {
    "limits": LimitsConfig,
    "llm": LlmConfig,
    "maintenance": MaintenanceConfig,
}


def default_config() -> dict[str, dict[str, Any]]:
    """Wartości domyślne wszystkich sekcji konfiguracji."""
    return {
        "limits": LimitsConfig().model_dump(),
        "llm": LlmConfig().model_dump(),
        "maintenance": MaintenanceConfig().model_dump(),
        "feature_flags": dict(DEFAULT_FEATURE_FLAGS),
    }


def _validate_section(name: str, value: dict[str, Any]) -> dict[str, Any]:
    """Waliduje scaloną sekcję; zwraca znormalizowane wartości."""
    model = _SECTION_MODELS.get(name)
    if model is None:  # feature_flags — dowolne flagi bool
        if not all(isinstance(flag, bool) for flag in value.values()):
            raise ValidationError("Flagi funkcji muszą być wartościami logicznymi")
        return dict(value)
    try:
        return model(**value).model_dump()
    except pydantic.ValidationError as exc:
        raise ValidationError(f"Niepoprawna konfiguracja sekcji '{name}'") from exc


async def _load_rows(db: AsyncSession) -> dict[str, PlatformSetting]:
    result = await db.execute(select(PlatformSetting))
    return {row.key: row for row in result.scalars().all() if row.key in CONFIG_SECTIONS}


async def get_config(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Zwraca pełną konfigurację: wartości domyślne nadpisane zapisem z bazy."""
    config = default_config()
    for key, row in (await _load_rows(db)).items():
        config[key] = {**config[key], **(row.value or {})}
    return config


async def update_config(
    db: AsyncSession,
    *,
    admin: User,
    sections: dict[str, dict[str, Any]],
    ip_address: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Scala podane sekcje z bieżącą konfiguracją i zapisuje zmiany."""
    unknown = set(sections) - set(CONFIG_SECTIONS)
    if unknown:
        raise ValidationError(f"Nieznane sekcje konfiguracji: {', '.join(sorted(unknown))}")

    rows = await _load_rows(db)
    config = default_config()
    for key, row in rows.items():
        config[key] = {**config[key], **(row.value or {})}

    changes: dict[str, dict[str, Any]] = {}
    for name, partial in sections.items():
        merged = _validate_section(name, {**config[name], **partial})
        if merged == config[name]:
            continue
        changes[name] = {"old": config[name], "new": merged}
        config[name] = merged

        row = rows.get(name)
        if row is None:
            db.add(PlatformSetting(key=name, value=merged, updated_by=admin.id))
        else:
            row.value = merged
            row.updated_by = admin.id

    if changes:
        await log_action(
            db,
            tenant_id=uuid.UUID(NIL_UUID),
            user_id=admin.id,
            action="platform.config_updated",
            resource_type="platform_config",
            resource_id=uuid.UUID(NIL_UUID),
            changes=changes,
            ip_address=ip_address,
        )

    return config
