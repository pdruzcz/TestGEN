"""HTTP cookie helpers for JWT auth tokens."""

from fastapi import Response

from app.core.config import get_settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
        max_age=settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key="access_token",
        path="/api",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
