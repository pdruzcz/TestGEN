"""Notification schemas — Story 7.11 (AC3/AC4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationSeverity, NotificationType


class NotificationOut(BaseModel):
    """Rekord powiadomienia in-app (lista dzwonka, AC3)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    severity: NotificationSeverity
    title: str
    message: str
    resource_type: str | None = None
    current_value: int | None = None
    limit_value: int | None = None
    percentage: int | None = None
    threshold_percentage: int | None = None
    is_read: bool
    cta_url: str | None = None
    created_at: datetime


class NotificationListOut(BaseModel):
    """Strona listy GET /notifications (AC3)."""

    items: list[NotificationOut]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=100)


class UnreadCountOut(BaseModel):
    """Badge dzwonka GET /notifications/unread-count (AC3)."""

    count: int


class MarkAllReadOut(BaseModel):
    """POST /notifications/read-all — liczba oznaczonych (AC3)."""

    updated: int
