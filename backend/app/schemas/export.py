"""Schematy eksportu do systemów zarządzania testami — Story 8.8 (AC1, AC2, AC4).

Klucz API TestRaila występuje wyłącznie w żądaniach. Odpowiedź niesie tylko
informację, że poświadczenia są zapisane — sam klucz zostaje w bazie
zaszyfrowany i nie wraca żadnym endpointem.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TestRailConfigRequest(BaseModel):
    """Konfiguracja integracji z TestRailem (AC1/AC4)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "base_url": "https://twojafirma.testrail.io",
                "email": "qa@twojafirma.pl",
                "api_key": "klucz-api-z-testrail",
                "testrail_project_id": 12,
                "priority_map": {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1},
            }
        },
    )

    base_url: str = Field(min_length=1, max_length=500, description="Adres instancji TestRail (HTTPS)")
    email: str = Field(min_length=1, max_length=255, description="E-mail konta TestRail")
    api_key: str = Field(min_length=1, description="Klucz API z profilu TestRail")
    testrail_project_id: int = Field(ge=1, description="Identyfikator projektu docelowego")
    suite_id: int | None = Field(default=None, ge=1, description="Suite (tryb multi-suite)")
    # Mapowania są opcjonalne — bez nich obowiązują wartości domyślne (AC4).
    priority_map: dict[str, int] | None = None
    type_map: dict[str, int] | None = None
    field_mapping: dict[str, str] | None = None


class TestRailConfigResponse(BaseModel):
    """Zapisana konfiguracja — bez klucza API (AC1)."""

    id: uuid.UUID
    project_id: uuid.UUID
    base_url: str
    email: str
    testrail_project_id: int | None = None
    suite_id: int | None = None
    priority_map: dict[str, int]
    type_map: dict[str, int]
    field_mapping: dict[str, str]
    is_active: bool
    created_at: datetime


class TestRailTestConnectionResponse(BaseModel):
    """Wynik sprawdzenia połączenia z instancją (AC1)."""

    connected: bool
    message: str
    project_name: str | None = None


class TmsExportRequest(BaseModel):
    """Żądanie eksportu; pusta lista oznacza wszystkie przypadki projektu."""

    model_config = ConfigDict(extra="ignore")

    test_case_ids: list[uuid.UUID] = Field(default_factory=list)


class TmsExportAcceptedResponse(BaseModel):
    """Eksport przyjęty do realizacji w tle (AC2).

    Postęp śledzi się pod ``status_url`` — tym samym mechanizmem, co analizy.
    """

    task_id: str
    status: str = "pending"
    status_url: str
    test_cases: int


# ── Story 8.9: Jira Xray i Zephyr Scale ─────────────────────────────────────

JiraPlugin = Literal["xray", "zephyr"]


class JiraConfigRequest(BaseModel):
    """Konfiguracja integracji z Jirą przez wtyczkę testową (AC1/AC5)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "base_url": "https://twojafirma.atlassian.net",
                "email": "qa@twojafirma.pl",
                "api_token": "token-api-atlassian",
                "project_key": "QA",
                "plugin": "xray",
                "linked_issue": "QA-42",
            }
        },
    )

    base_url: str = Field(min_length=1, max_length=500, description="Adres instancji Jira (HTTPS)")
    email: str = Field(min_length=1, max_length=255, description="E-mail konta Atlassian")
    api_token: str = Field(min_length=1, description="Token API z konta Atlassian")
    project_key: str = Field(min_length=1, max_length=50, description="Klucz projektu Jira, np. QA")
    plugin: JiraPlugin = Field(description="Wtyczka testowa: xray albo zephyr")
    # Historyjka lub wymaganie, z którym wiążemy eksportowane testy (AC2/AC3).
    linked_issue: str | None = Field(default=None, max_length=50)
    priority_map: dict[str, str] | None = None
    type_labels: dict[str, str] | None = None


class JiraConfigResponse(BaseModel):
    """Zapisana konfiguracja — bez tokenu (AC1)."""

    id: uuid.UUID
    project_id: uuid.UUID
    base_url: str
    email: str
    project_key: str
    plugin: str
    linked_issue: str | None = None
    priority_map: dict[str, str]
    type_labels: dict[str, str]
    is_active: bool
    created_at: datetime


class JiraTestConnectionResponse(BaseModel):
    """Wynik sprawdzenia połączenia z instancją Jiry (AC1)."""

    connected: bool
    message: str
    project_name: str | None = None
    account: str | None = None
