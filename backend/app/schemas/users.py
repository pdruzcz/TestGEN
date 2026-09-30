"""User-related Pydantic schemas."""

import json
import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import RoleEnum, _validate_password_complexity

_MAX_PREFERENCES_SIZE = 4096  # max JSON size in bytes
_MAX_PREFERENCES_DEPTH = 3  # max nesting depth


def _check_depth(obj: object, max_depth: int, current: int = 0) -> None:
    """Reject deeply nested structures to prevent abuse."""
    if current > max_depth:
        raise ValueError(f"Notification preferences nesting exceeds max depth of {max_depth}")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_depth(v, max_depth, current + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth(item, max_depth, current + 1)


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    name: str
    role: RoleEnum
    is_active: bool
    is_blocked: bool = False
    deleted_at: datetime | None = None
    email_verified_at: datetime | None = None
    notification_preferences: dict = {}
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    mfa_enabled: bool = False

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    notification_preferences: dict | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Name cannot be blank")
            return stripped
        return v

    @field_validator("notification_preferences")
    @classmethod
    def validate_preferences_size(cls, v: dict | None) -> dict | None:
        if v is not None:
            _check_depth(v, _MAX_PREFERENCES_DEPTH)
            try:
                serialized = json.dumps(v)
            except (RecursionError, TypeError, ValueError) as e:
                raise ValueError("Invalid notification preferences structure") from e
            if len(serialized) > _MAX_PREFERENCES_SIZE:
                raise ValueError(f"Notification preferences must be under {_MAX_PREFERENCES_SIZE} bytes")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class ChangeableRole(StrEnum):
    USER = "user"
    OWNER = "owner"


class ChangeRoleRequest(BaseModel):
    role: ChangeableRole


class PlanEnum(StrEnum):
    """Model 3-planowy (CR#2 2026-08-28) — zgodny z Tenant.plan."""

    FREEMIUM = "freemium"
    BASIC = "basic"
    PREMIUM = "premium"


class ChangePlanRequest(BaseModel):
    plan: PlanEnum


class ChangePlanResponse(BaseModel):
    message: str
    tenant_id: str
    plan: str


class ResetPasswordByTokenRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)
