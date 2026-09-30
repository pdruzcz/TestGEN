"""Auth API routes: registration, email verification, invitation, login, refresh, logout, MFA."""

import logging
import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ConflictError
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.auth import (
    AcceptInvitationRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    SelectTenantRequest,
    TenantInfo,
    VerifyEmailRequest,
)
from app.services.admin.audit_service import log_action
from app.services.auth.auth_service import (
    accept_invitation,
    login,
    logout,
    refresh_tokens,
    register,
    select_tenant,
    verify_email,
)
from app.services.auth.mfa_service import confirm_mfa, disable_mfa, regenerate_backup_codes, setup_mfa, verify_mfa_login
from app.workers.tasks.email_tasks import send_verification_email_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register_user(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        user, token = await register(
            db,
            email=body.email,
            password=body.password,
            company_name=body.company_name,
            nip=body.nip,
        )
    except ConflictError as exc:
        if exc.extra.get("field") == "nip":
            # NIP is a public business identifier — return real 409
            raise
        # Email conflict: return generic success to prevent email enumeration
        return RegisterResponse(email=body.email)

    # Commit before dispatching Celery task to avoid sending emails for uncommitted data
    await db.commit()

    try:
        send_verification_email_task.delay(user.email, token, user.name)
    except Exception:
        logger.exception("Failed to queue verification email for %s", user.email)

    response.headers["Location"] = f"/api/v1/users/{user.id}"
    return RegisterResponse(email=user.email)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email_route(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    await verify_email(db, body.token)
    await db.commit()
    return {"message": "Adres e-mail został zweryfikowany"}


@router.post("/accept-invitation", response_model=MessageResponse)
async def accept_invitation_route(
    body: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    await accept_invitation(db, token=body.token, password=body.password)
    await db.commit()
    return {"message": "Zaproszenie zostało zaakceptowane"}


@router.post("/login", response_model=LoginResponse)
async def login_route(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip_address = request.client.host if request.client else None
    result = await login(db, redis, body.email, body.password, ip_address)
    await db.commit()

    if result.tenants_required:
        return LoginResponse(
            message="Wybierz organizację",
            tenants_required=True,
            pre_auth_token=result.pre_auth_token,
            tenants=[
                TenantInfo(
                    tenant_id=t["tenant_id"],
                    tenant_name=t["tenant_name"],
                    role=t["role"],
                )
                for t in result.tenants
            ],
        )

    if result.mfa_required:
        return LoginResponse(
            message="Wymagana weryfikacja MFA",
            mfa_required=True,
            mfa_token=result.mfa_token,
        )

    set_auth_cookies(response, result.access_token, result.refresh_token)
    return LoginResponse()


@router.post("/select-tenant", response_model=LoginResponse)
async def select_tenant_route(
    body: SelectTenantRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip_address = request.client.host if request.client else None
    result = await select_tenant(db, redis, body.pre_auth_token, body.tenant_id, ip_address)
    await db.commit()

    if result.mfa_required:
        return LoginResponse(
            message="Wymagana weryfikacja MFA",
            mfa_required=True,
            mfa_token=result.mfa_token,
        )

    set_auth_cookies(response, result.access_token, result.refresh_token)
    return LoginResponse()


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_route(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(None),
):
    if not refresh_token:
        from app.core.exceptions import AuthError

        raise AuthError("Missing refresh token")

    access_tok, refresh_tok = await refresh_tokens(db, redis, refresh_token)
    await db.commit()
    set_auth_cookies(response, access_tok, refresh_tok)
    return RefreshResponse()


@router.post("/logout", response_model=MessageResponse)
async def logout_route(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
):
    # Extract user info for audit before revoking tokens
    user_id = None
    tenant_id = None
    if access_token:
        try:
            from app.services.auth.jwt_handler import decode_token

            payload = decode_token(access_token)
            user_id = payload.get("sub")
            tenant_id = payload.get("tenant_id")
        except Exception:
            pass  # graceful — log what we can

    await logout(redis, access_token, refresh_token)
    clear_auth_cookies(response)

    if user_id and tenant_id:
        try:
            uid = uuid.UUID(user_id)
            tid = uuid.UUID(tenant_id)
        except (ValueError, TypeError):
            logger.warning("Invalid user_id/tenant_id in logout token payload")
            return {"message": "Wylogowano pomyślnie"}

        try:
            await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))
            await log_action(
                db,
                tenant_id=tid,
                user_id=uid,
                action="user.logout",
                resource_type="user",
                resource_id=uid,
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to log logout action")

    return {"message": "Wylogowano pomyślnie"}


# --- MFA endpoints ---


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup_route(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    result = await setup_mfa(db, current_user.id, current_user.email)
    await db.commit()
    return result


@router.post("/mfa/confirm", response_model=MfaConfirmResponse)
async def mfa_confirm_route(
    body: MfaConfirmRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    backup_codes = await confirm_mfa(db, current_user.id, body.code)
    await db.commit()
    return MfaConfirmResponse(backup_codes=backup_codes)


@router.post("/mfa/verify", response_model=LoginResponse)
async def mfa_verify_route(
    body: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip_address = request.client.host if request.client else None

    # Rate limit MFA attempts per token (max 5 attempts)
    from app.services.auth.jwt_handler import decode_token as _decode
    from app.services.auth.token_store import increment_mfa_attempts

    try:
        mfa_payload = _decode(body.mfa_token)
        # Rate limit by user (sub claim), not jti — prevents rotating invalid tokens
        rate_limit_key = mfa_payload.get("sub", body.mfa_token[:32])
    except Exception:
        # For invalid tokens, hash the token to limit rotation
        import hashlib

        token_hash = hashlib.sha256(body.mfa_token.encode()).hexdigest()[:16]
        rate_limit_key = f"invalid:{token_hash}"
    attempts = await increment_mfa_attempts(redis, rate_limit_key)
    if attempts > 5:
        from app.core.exceptions import AuthError

        raise AuthError("Too many MFA verification attempts. Please login again.")

    access_tok, refresh_tok = await verify_mfa_login(db, redis, body.mfa_token, body.code, ip_address)
    await db.commit()
    set_auth_cookies(response, access_tok, refresh_tok)
    return LoginResponse()


@router.delete("/mfa", response_model=MessageResponse)
async def mfa_disable_route(
    body: MfaDisableRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    await disable_mfa(db, current_user.id, body.password)
    await db.commit()
    return {"message": "MFA zostało wyłączone"}


@router.post("/mfa/backup-codes", response_model=MfaConfirmResponse)
async def mfa_regenerate_backup_codes_route(
    body: MfaDisableRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    backup_codes = await regenerate_backup_codes(db, current_user.id, body.password)
    await db.commit()
    return MfaConfirmResponse(backup_codes=backup_codes, message="Kody zapasowe zostały wygenerowane ponownie")
