"""Schematy kluczy API — Story 8.6 (AC1, AC5).

Klucz plaintext występuje w dokładnie jednym miejscu kontraktu —
``CreateApiKeyResponse.key``. Schemat listy (``ApiKeyResponse``) nie ma
takiego pola, więc nawet przypadkowa zmiana kodu nie ujawni klucza
ponownie.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.api_key import ApiKeyScope, ApiKeyStatus


class CreateApiKeyRequest(BaseModel):
    """Parametry nowego klucza (AC1)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jenkins — produkcja",
                "scope": "full_access",
                "expires_at": "2027-01-15T23:59:59Z",
            }
        }
    )

    name: str = Field(min_length=1, max_length=100, description="Opisowa nazwa klucza")
    scope: ApiKeyScope = Field(
        default=ApiKeyScope.READ_ONLY,
        description="read_only — tylko odczyt; full_access — pełny dostęp",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Data wygaśnięcia (opcjonalna, maksymalnie 2 lata od dziś)",
    )


class ApiKeyResponse(BaseModel):
    """Klucz na liście — bez hasha i bez plaintextu (AC5)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    scope: ApiKeyScope
    key_prefix: str
    status: ApiKeyStatus
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class CreateApiKeyResponse(BaseModel):
    """Odpowiedź tworzenia — jedyne miejsce z pełnym kluczem (AC1)."""

    key: str = Field(description="Pełny klucz — wyświetlany tylko raz, nie da się go odzyskać")
    api_key: ApiKeyResponse


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]
    total: int
