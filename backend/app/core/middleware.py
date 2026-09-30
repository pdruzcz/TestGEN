import re
import secrets
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings


def setup_cors(app: FastAPI) -> None:
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-TestGEN-Tenant-Id", "X-XSRF-TOKEN"],
        expose_headers=["X-Total-Count", "Link", "X-Request-ID", "Content-Disposition"],
    )


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID header for request tracing."""

    _REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_id = request.headers.get("X-Request-ID")
        # Validate format to prevent log injection (max 64 chars, alphanumeric/UUID)
        request_id = client_id if client_id and self._REQUEST_ID_RE.match(client_id) else str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response


class CSRFCookieMiddleware(BaseHTTPMiddleware):
    """Sets XSRF-TOKEN cookie for Angular's XSRF protection.

    Double-submit cookie pattern:
    1. Server sets XSRF-TOKEN cookie (httponly=False so JS can read it)
    2. Angular reads cookie and sends value as X-XSRF-TOKEN header
    3. Server verifies header matches cookie on state-changing requests

    CSRF validation is only enforced when an auth cookie is present,
    preventing interference with stateless API calls.
    """

    _CSRF_COOKIE = "XSRF-TOKEN"
    _CSRF_HEADER = "X-XSRF-TOKEN"
    _AUTH_COOKIE = "access_token"  # Cookie sent on all /api/* requests (path="/api")
    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        csrf_cookie = request.cookies.get(self._CSRF_COOKIE)
        has_auth_cookie = self._AUTH_COOKIE in request.cookies

        # Validate CSRF on state-changing requests whenever cookie-based auth is active
        if request.method not in self._SAFE_METHODS and has_auth_cookie:
            csrf_header = request.headers.get(self._CSRF_HEADER)
            if not csrf_cookie or csrf_header != csrf_cookie:
                return Response(
                    content='{"type":"https://testgen.io/errors/csrf-error","title":"CSRF Validation Failed","status":403,"detail":"CSRF token mismatch"}',
                    status_code=403,
                    media_type="application/problem+json",
                )

        response = await call_next(request)

        # Set CSRF cookie if not present, OR refresh on login/logout (M5: prevent token fixation)
        is_auth_state_change = request.url.path.endswith(("/auth/login", "/auth/logout"))
        if not csrf_cookie or (is_auth_state_change and response.status_code < 400):
            token = secrets.token_hex(32)
            response.set_cookie(
                key=self._CSRF_COOKIE,
                value=token,
                httponly=False,  # Angular JS must read this cookie
                samesite="lax",
                secure=get_settings().cookie_secure,
                path="/",
            )

        return response


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware in correct order (outermost first)."""
    from app.core.config_billing import get_billing_settings
    from app.middleware.rate_limit import RateLimitMiddleware

    setup_cors(app)
    app.add_middleware(CSRFCookieMiddleware)
    # Rate limiting per tenant (Story 7.8, AC2/AC5) — przed autoryzacją;
    # RequestID rejestrowany później = zewnętrzny (X-Request-ID także na 429).
    if get_billing_settings().rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)
