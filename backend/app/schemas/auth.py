"""Auth-related Pydantic schemas."""

import re
import uuid
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, field_validator


class RoleEnum(StrEnum):
    USER = "user"
    OWNER = "owner"
    ADMIN = "admin"


def _validate_password_complexity(password: str) -> str:
    """Ensure password has at least one uppercase, one lowercase, one digit, and one special char."""
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character")
    return password


def _validate_nip(nip: str) -> str:
    """Validate Polish NIP with modulo 11 checksum."""
    if not re.match(r"^\d{10}$", nip):
        raise ValueError("NIP must be exactly 10 digits")
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    checksum = sum(int(nip[i]) * w for i, w in enumerate(weights)) % 11
    if checksum != int(nip[9]):
        raise ValueError("Invalid NIP checksum")
    return nip


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    company_name: str = Field(min_length=1, max_length=255)
    nip: str | None = Field(None)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Company name cannot be blank")
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("Company name cannot contain newline characters")
        return stripped

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @field_validator("nip")
    @classmethod
    def nip_checksum(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        if v is not None:
            return _validate_nip(v)
        return v


class RegisterResponse(BaseModel):
    email: str
    message: str = "E-mail weryfikacyjny wysłany. Sprawdź swoją skrzynkę."


class MessageResponse(BaseModel):
    message: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class InviteRoleEnum(StrEnum):
    USER = "user"
    OWNER = "owner"


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: InviteRoleEnum = InviteRoleEnum.USER


class InviteResponse(BaseModel):
    message: str
    user_id: uuid.UUID


# --- Login / Auth flow ---


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TenantInfo(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    role: RoleEnum


class LoginResponse(BaseModel):
    message: str = "Zalogowano pomyślnie"
    mfa_required: bool = False
    mfa_token: str | None = None
    tenants_required: bool = False
    pre_auth_token: str | None = None
    tenants: list[TenantInfo] | None = None


class SelectTenantRequest(BaseModel):
    pre_auth_token: str = Field(min_length=1)
    tenant_id: uuid.UUID


class RefreshResponse(BaseModel):
    message: str = "Token odświeżony"


# --- MFA ---


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaConfirmResponse(BaseModel):
    backup_codes: list[str]
    message: str = "MFA zostało włączone"


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=8)


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
