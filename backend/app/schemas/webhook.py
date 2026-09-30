"""Schematy webhooków wychodzących — Story 8.7 (AC1, AC5, AC6).

Sekret występuje wyłącznie w żądaniach. Żaden schemat odpowiedzi go nie ma,
więc nawet przypadkowa zmiana kodu nie ujawni go po zapisaniu — odbiorca
ma swoją kopię i to ona służy do weryfikacji podpisu.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.outbound_webhook import WebhookEventType

EventLiteral = Literal[
    "analysis.completed",
    "security.finding",
    "gap.detected",
    "export.ready",
    "subscription.changed",
]


class CreateWebhookRequest(BaseModel):
    """Nowy webhook (AC1)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "url": "https://twoj-system.pl/testgen-hook",
                "secret": "zmien-mnie-na-wlasny-sekret",
                "events": ["analysis.completed", "security.finding"],
                "description": "Kanał #dyzur na Slacku",
            }
        },
    )

    url: str = Field(min_length=1, max_length=2048, description="Adres HTTPS endpointu")
    secret: str = Field(min_length=16, description="Sekret do podpisu HMAC-SHA256")
    events: list[EventLiteral] = Field(min_length=1, description="Subskrybowane typy zdarzeń")
    description: str | None = Field(default=None, max_length=200)


class UpdateWebhookRequest(BaseModel):
    """Zmiana webhooka; pominięte pola zostają bez zmian.

    Pusty ``secret`` oznacza „nie zmieniaj" — zmiana adresu czy listy zdarzeń
    nie powinna wymagać ponownego podawania sekretu.
    """

    model_config = ConfigDict(extra="ignore")

    url: str | None = Field(default=None, max_length=2048)
    secret: str | None = Field(default=None)
    events: list[EventLiteral] | None = None
    description: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    """Webhook na liście — bez sekretu (AC1/AC6)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    description: str | None = None
    events: list[str]
    is_active: bool
    last_delivery_at: datetime | None = None
    last_delivery_status: str | None = None
    created_at: datetime


class WebhookListResponse(BaseModel):
    items: list[WebhookResponse]
    total: int
    # Katalog dostępnych zdarzeń — frontend nie musi ich powielać.
    available_events: list[str] = Field(
        default_factory=lambda: [e.value for e in WebhookEventType]
    )


class TestWebhookResponse(BaseModel):
    """Wynik testowego pinga (AC1)."""

    success: bool
    status_code: int | None = None
    message: str
    response_body: str | None = None


class WebhookDeliveryResponse(BaseModel):
    """Pojedyncza próba dostarczenia w historii (AC5)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    status: str
    attempt_number: int
    response_status: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    delivered_at: datetime | None = None
    next_retry_at: datetime | None = None
    created_at: datetime


class WebhookDeliveryListResponse(BaseModel):
    items: list[WebhookDeliveryResponse]
    total: int
