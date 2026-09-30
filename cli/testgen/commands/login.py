"""Komendy ``login``/``logout``/``whoami`` — Story 8.10 (AC1)."""

from typing import Any

from testgen import auth
from testgen import client as client_module
from testgen.client import TestGENClient
from testgen.config import Config
from testgen.errors import AuthError, CliError
from testgen.output import Printer


def login_with_api_key(config: Config, printer: Printer, api_key: str) -> dict[str, Any]:
    """Sprawdza klucz przed zapisaniem — inaczej błąd wyszedłby dopiero przy analizie."""
    probe = TestGENClient(config.api_url, api_key, config.timeout)
    identity = probe.whoami()
    path = auth.save_credentials(api_key, api_url=config.api_url, kind="api_key")
    result = _identity_view(identity, config.api_url, "api_key")
    printer.result(result)
    printer.success(f"Zalogowano jako {result['email']}; poświadczenia w {path}")
    return result


def login_with_password(
    config: Config, printer: Printer, email: str, password: str, tenant_id: str | None = None
) -> dict[str, Any]:
    payload = client_module.password_login(config.api_url, email, password, config.timeout)

    if payload.get("mfa_required"):
        raise AuthError(
            "Konto wymaga weryfikacji MFA",
            hint="CLI nie obsługuje MFA — wygeneruj klucz API i użyj `testgen login --api-key`.",
        )

    token = payload.get("access_token")
    if payload.get("tenants_required"):
        token = _resolve_tenant(config, printer, payload, tenant_id)
    if not token:
        raise AuthError("Serwer nie zwrócił tokenu dostępu")

    path = auth.save_credentials(token, api_url=config.api_url, kind="jwt")
    identity = TestGENClient(config.api_url, token, config.timeout).whoami()
    result = _identity_view(identity, config.api_url, "jwt")
    printer.result(result)
    printer.success(f"Zalogowano jako {result['email']}; poświadczenia w {path}")
    # Token sesyjny wygasa po kilkudziesięciu minutach; w CI to pułapka,
    # bo pipeline zadziała raz, a za godzinę przestanie.
    printer.warning("Token sesji wygasa — do CI/CD użyj klucza API (testgen login --api-key).")
    return result


def _resolve_tenant(
    config: Config, printer: Printer, payload: dict[str, Any], tenant_id: str | None
) -> str:
    tenants = payload.get("tenants") or []
    pre_auth_token = payload.get("pre_auth_token") or ""
    if not tenant_id:
        if len(tenants) != 1:
            names = ", ".join(f"{t.get('tenant_name')} ({t.get('tenant_id')})" for t in tenants)
            raise CliError(
                "Konto należy do kilku organizacji",
                hint=f"Wskaż --tenant-id. Dostępne: {names}",
            )
        tenant_id = str(tenants[0].get("tenant_id"))
        printer.info(f"Wybrano organizację {tenants[0].get('tenant_name')}")
    return client_module.select_tenant(config.api_url, pre_auth_token, tenant_id, config.timeout)


def logout(printer: Printer) -> dict[str, Any]:
    removed = auth.clear_credentials()
    result = {"removed": removed, "path": str(auth.AUTH_PATH)}
    printer.result(result)
    if removed:
        printer.success("Usunięto zapisane poświadczenia")
    else:
        printer.info("Nie było zapisanych poświadczeń")
    return result


def whoami(client: TestGENClient, config: Config, printer: Printer) -> dict[str, Any]:
    stored = auth.load_credentials()
    kind = str(stored.get("kind")) if stored and not config.api_key else "api_key"
    result = _identity_view(client.whoami(), config.api_url, kind)
    printer.result(result)
    return result


def _identity_view(identity: dict[str, Any], api_url: str, kind: str) -> dict[str, Any]:
    return {
        "email": identity.get("email", ""),
        "name": identity.get("name") or "",
        "user_id": str(identity.get("id") or ""),
        "tenant_id": str(identity.get("tenant_id") or ""),
        "role": identity.get("role") or "",
        "api_url": api_url,
        "credential": kind,
    }
