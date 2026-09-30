"""Integracje z hostingiem kodu — GitHub (Story 8.1) i GitLab (Story 8.2).

Osobny moduł od ``integrations.py``: tamten router ma prefiks ``/projects``
i obsługuje trackery (Jira/ADO) w kontekście projektu, te endpointy są
tenant-scoped i żyją pod ``/integrations``.

Przepływ OAuth jest dwuetapowy, bo GitHub daje jeden token na użytkownika,
a repozytoria wybiera się dopiero potem:

1. ``/authorize`` → URL GitHuba (``state`` w Redisie, TTL 10 min)
2. ``/callback`` → token do Redisu (TTL 30 min), przekierowanie na frontend
3. ``/available-repos`` → lista repozytoriów spod tokenu
4. ``POST /repos`` → zapis integracji (token zaszyfrowany) + webhook u dostawcy

GitLab przechodzi tę samą ścieżkę, z trzema różnicami: adres instancji jest
konfigurowalny (self-hosted), projekt adresuje się liczbą zamiast nazwą
``owner/repo``, a webhook uwierzytelnia się powtórzonym sekretem
(``X-Gitlab-Token``) zamiast podpisem HMAC.

Endpointy webhooków są **nieuwierzytelnione** — wywołuje je dostawca, nie
przeglądarka. Ich jedyną bramą jest podpis/sekret (AC5).
"""

import json
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import NIL_UUID
from app.core.dependencies import (
    _set_rls_tenant,
    get_current_user,
    get_db,
    get_redis,
    get_tenant,
)
from app.core.encryption import decrypt_token, encrypt_token
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.integration import (
    IntegrationEvent,
    ScmEventStatus,
    ScmIntegration,
    ScmProvider,
)
from app.models.user import User
from app.schemas.integration import (
    ConnectGitLabProjectRequest,
    ConnectRepoRequest,
    GitLabProjectOption,
    IntegrationEventResponse,
    ScmIntegrationListResponse,
    ScmIntegrationResponse,
    ScmRepoOption,
    StatusCheckConfigRequest,
    StatusCheckConfigResponse,
    WebhookAckResponse,
)
from app.services.admin.audit_service import log_action
from app.services.integrations import github_service, gitlab_service, scm_webhook_service
from app.services.integrations.status_check_builder import STATUS_CONTEXT, normalize_threshold

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations-scm"])

_STATE_TTL_SECONDS = 600  # 10 min na dokończenie autoryzacji u dostawcy
_TOKEN_TTL_SECONDS = 1800  # 30 min na wybór repozytoriów po powrocie


def _state_key(state: str) -> str:
    return f"github:oauth_state:{state}"


def _token_key(provider: ScmProvider, user_id: uuid.UUID) -> str:
    return f"{provider.value}:oauth_token:{user_id}"


def _webhook_url(provider: ScmProvider) -> str:
    base = get_settings().api_public_base_url.rstrip("/")
    return f"{base}/api/v1/integrations/{provider.value}/webhook"


def _to_response(integration: ScmIntegration) -> ScmIntegrationResponse:
    config = integration.config or {}
    return ScmIntegrationResponse(
        id=integration.id,
        provider=integration.provider.value,
        repo_full_name=integration.repo_full_name,
        repo_url=integration.repo_url,
        default_branch=integration.default_branch,
        project_id=integration.project_id,
        webhook_active=integration.hook_id is not None,
        is_active=integration.is_active,
        created_at=integration.created_at,
        gitlab_url=config.get("gitlab_url"),
    )


async def _list_active(
    db: AsyncSession, tenant_id: uuid.UUID, provider: ScmProvider
) -> list[ScmIntegration]:
    """Aktywne integracje firmy dla danego dostawcy, najnowsze pierwsze."""
    result = await db.execute(
        select(ScmIntegration)
        .where(
            ScmIntegration.tenant_id == tenant_id,
            ScmIntegration.provider == provider,
            ScmIntegration.is_active.is_(True),
        )
        .order_by(ScmIntegration.created_at.desc())
    )
    return list(result.scalars().all())


async def _recent_events(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    provider: ScmProvider,
    integration_id: uuid.UUID | None,
    limit: int,
) -> list[IntegrationEventResponse]:
    """Ostatnie zdarzenia dostawcy — join po integracji filtruje provider."""
    stmt = (
        select(IntegrationEvent)
        .join(ScmIntegration, ScmIntegration.id == IntegrationEvent.integration_id)
        .where(
            IntegrationEvent.tenant_id == tenant_id,
            ScmIntegration.provider == provider,
        )
        .order_by(IntegrationEvent.created_at.desc())
        .limit(limit)
    )
    if integration_id is not None:
        stmt = stmt.where(IntegrationEvent.integration_id == integration_id)

    events = (await db.execute(stmt)).scalars().all()
    return [
        IntegrationEventResponse(
            id=e.id,
            event_type=e.event_type.value,
            action=e.action,
            repo_full_name=e.repo_full_name,
            branch=e.branch,
            base_branch=e.base_branch,
            commit_sha=e.commit_sha,
            pr_number=e.pr_number,
            status=e.status.value,
            task_id=e.task_id,
            error_message=e.error_message,
            created_at=e.created_at,
            completed_at=e.completed_at,
        )
        for e in events
    ]


async def _find_by_repo_any_tenant(
    db: AsyncSession, provider: ScmProvider, repo_full_name: str
) -> ScmIntegration | None:
    """Szuka integracji bez filtra tenanta — unikalność (provider, repo) jest globalna."""
    await _set_rls_tenant(db, NIL_UUID)
    return (
        await db.execute(
            select(ScmIntegration).where(
                ScmIntegration.provider == provider,
                ScmIntegration.repo_full_name == repo_full_name,
            )
        )
    ).scalar_one_or_none()


# ── OAuth ───────────────────────────────────────────────────────────────────


@router.get("/github/authorize")
async def github_authorize(
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    """URL autoryzacji GitHuba dla zalogowanego użytkownika (AC1).

    Zwracamy adres w ciele, a nie przekierowanie 302: żądanie idzie z SPA
    XHR-em, który przekierowania na obcą domenę i tak by nie wykonał.
    """
    if not github_service.is_configured():
        raise ValidationError(
            "Integracja z GitHub nie jest skonfigurowana — uzupełnij GITHUB_CLIENT_ID i GITHUB_CLIENT_SECRET"
        )

    state = secrets.token_urlsafe(32)
    await redis.set(
        _state_key(state),
        json.dumps({"user_id": str(current_user.id), "tenant_id": str(tenant_id)}),
        ex=_STATE_TTL_SECONDS,
    )
    return {"authorization_url": github_service.get_authorization_url(state)}


@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Odbiera powrót z GitHuba i odsyła użytkownika na frontend (AC1).

    Endpoint jest bez uwierzytelnienia — trafia tu przeglądarka po redirekcie
    z GitHuba, bez nagłówka Authorization. Tożsamość niesie ``state``, który
    wydaliśmy zalogowanemu użytkownikowi i który jest jednorazowy.
    """
    frontend = get_settings().frontend_base_url.rstrip("/")
    target = f"{frontend}/settings/integrations/github"

    raw_state = await redis.get(_state_key(state))
    if not raw_state:
        return RedirectResponse(f"{target}?error=invalid_state", status_code=302)
    await redis.delete(_state_key(state))  # jednorazowy — chroni przed replayem

    try:
        token_payload = await github_service.exchange_code_for_token(code)
    except Exception as exc:
        logger.warning("Wymiana kodu GitHuba nie powiodła się: %s", exc)
        return RedirectResponse(f"{target}?error=token_exchange", status_code=302)

    context = json.loads(raw_state)
    await redis.set(
        _token_key(ScmProvider.GITHUB, uuid.UUID(context["user_id"])),
        token_payload["access_token"],
        ex=_TOKEN_TTL_SECONDS,
    )
    return RedirectResponse(f"{target}?connected=1", status_code=302)


async def _resolve_access_token(
    db: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    provider: ScmProvider = ScmProvider.GITHUB,
) -> str:
    """Token ze świeżej autoryzacji, a w razie jej braku — z istniejącej integracji.

    Fallback na zapisaną integrację pozwala dołożyć kolejne repozytorium bez
    ponownego przechodzenia przez OAuth, dopóki token jest ważny.
    """
    cached = await redis.get(_token_key(provider, user_id))
    if cached:
        return cached if isinstance(cached, str) else cached.decode()

    existing = await _list_active(db, tenant_id, provider)
    if not existing:
        label = "GitHub" if provider == ScmProvider.GITHUB else "GitLab"
        raise ValidationError(f"Brak aktywnej autoryzacji {label} — połącz konto ponownie")
    return decrypt_token(existing[0].access_token_encrypted, tenant_id)


# ── repozytoria ─────────────────────────────────────────────────────────────


@router.get("/github/available-repos", response_model=list[ScmRepoOption])
async def list_available_repos(
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[ScmRepoOption]:
    """Repozytoria widoczne dla autoryzacji GitHub, z oznaczeniem podłączonych (AC1)."""
    access_token = await _resolve_access_token(db, redis, current_user.id, tenant_id)
    repos = await github_service.get_user_repos(access_token)

    connected = {
        row
        for row in (
            await db.execute(
                select(ScmIntegration.repo_full_name).where(
                    ScmIntegration.tenant_id == tenant_id,
                    ScmIntegration.provider == ScmProvider.GITHUB,
                    ScmIntegration.is_active.is_(True),
                )
            )
        ).scalars()
    }

    return [
        ScmRepoOption(
            full_name=repo["full_name"],
            name=repo["name"],
            private=bool(repo.get("private")),
            default_branch=repo.get("default_branch") or "main",
            html_url=repo.get("html_url") or "",
            clone_url=repo.get("clone_url") or "",
            connected=repo["full_name"] in connected,
        )
        for repo in repos
    ]


@router.get("/github/repos", response_model=ScmIntegrationListResponse)
async def list_connected_repos(
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> ScmIntegrationListResponse:
    """Podłączone repozytoria firmy wraz ze statusem webhooka (AC1/AC6)."""
    items = [_to_response(i) for i in await _list_active(db, tenant_id, ScmProvider.GITHUB)]
    return ScmIntegrationListResponse(
        items=items,
        total=len(items),
        provider_configured=github_service.is_configured(),
    )


@router.post("/github/repos", response_model=ScmIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def connect_repo(
    body: ConnectRepoRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ScmIntegrationResponse:
    """Podłącza repozytorium i rejestruje na nim webhook (AC1/AC2)."""
    access_token = await _resolve_access_token(db, redis, current_user.id, tenant_id)

    # Unikalność (provider, repo) jest globalna — sprawdzamy bez filtra tenanta,
    # żeby dać czytelny 409 zamiast błędu ograniczenia bazy.
    existing = await _find_by_repo_any_tenant(db, ScmProvider.GITHUB, body.full_name)
    await _set_rls_tenant(db, tenant_id)

    if existing is not None and existing.is_active:
        if existing.tenant_id != tenant_id:
            raise ConflictError("To repozytorium jest już podłączone do innej firmy w TestGEN")
        raise ConflictError("To repozytorium jest już podłączone")

    repos = await github_service.get_user_repos(access_token)
    repo = next((r for r in repos if r["full_name"] == body.full_name), None)
    if repo is None:
        raise NotFoundError("Repozytorium nie jest dostępne dla tej autoryzacji GitHub")

    webhook_secret = github_service.generate_webhook_secret()
    hook = await github_service.register_webhook(
        access_token, body.full_name, _webhook_url(ScmProvider.GITHUB), webhook_secret
    )

    if existing is not None:  # reaktywacja wcześniej odłączonego repozytorium
        integration = existing
        integration.tenant_id = tenant_id
        integration.user_id = current_user.id
        integration.is_active = True
    else:
        integration = ScmIntegration(
            tenant_id=tenant_id,
            user_id=current_user.id,
            provider=ScmProvider.GITHUB,
            repo_full_name=body.full_name,
            is_active=True,
        )
        db.add(integration)

    integration.repo_url = repo.get("clone_url") or repo.get("html_url") or ""
    integration.default_branch = repo.get("default_branch") or "main"
    integration.access_token_encrypted = encrypt_token(access_token, tenant_id)
    integration.webhook_secret_encrypted = encrypt_token(webhook_secret, tenant_id)
    integration.hook_id = str(hook.get("id")) if hook.get("id") is not None else None
    integration.config = {"private": bool(repo.get("private"))}
    await db.flush()

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.github.connected",
        resource_type="scm_integration",
        resource_id=integration.id,
        changes={"repo": body.full_name, "hook_id": integration.hook_id},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(integration)
    return _to_response(integration)


@router.delete("/github/repos/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repo(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Odłącza repozytorium i kasuje webhook u dostawcy (AC6)."""
    integration = (
        await db.execute(
            select(ScmIntegration).where(
                ScmIntegration.id == integration_id,
                ScmIntegration.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("Integracja nie została znaleziona")

    if integration.hook_id:
        try:
            access_token = decrypt_token(integration.access_token_encrypted, tenant_id)
            await github_service.delete_webhook(
                access_token, integration.repo_full_name, integration.hook_id
            )
        except Exception as exc:
            # Token mógł wygasnąć albo repo zniknąć — po naszej stronie i tak
            # odłączamy, inaczej martwa integracja zostałaby na liście na zawsze.
            logger.warning("Nie udało się usunąć webhooka na GitHubie: %s", exc)

    integration.is_active = False
    integration.hook_id = None
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.github.disconnected",
        resource_type="scm_integration",
        resource_id=integration.id,
        changes={"repo": integration.repo_full_name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/github/events", response_model=list[IntegrationEventResponse])
async def list_events(
    integration_id: uuid.UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationEventResponse]:
    """Ostatnie zdarzenia z webhooków GitHuba — domyślnie 10 (AC6)."""
    return await _recent_events(db, tenant_id, ScmProvider.GITHUB, integration_id, limit)


# ── webhook (bez uwierzytelnienia — bramą jest HMAC) ────────────────────────


@router.post("/github/webhook", response_model=WebhookAckResponse)
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
) -> WebhookAckResponse:
    """Przyjmuje zdarzenie z GitHuba, weryfikuje podpis i kolejkuje analizę.

    Odpowiadamy 200 także na zdarzenia, których nie obsługujemy — 4xx
    zniechęcałoby GitHuba do dalszych dostaw (po serii błędów wyłącza
    webhook). Odmowa dotyczy wyłącznie złego podpisu (AC5).
    """
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise ValidationError("Nieprawidłowy JSON w ciele webhooka") from None

    repo_full_name = (payload.get("repository") or {}).get("full_name")
    if not repo_full_name:
        return WebhookAckResponse(status="ignored", detail="Payload bez repozytorium")

    # Webhook przychodzi anonimowo — tenanta poznajemy dopiero z integracji.
    await _set_rls_tenant(db, NIL_UUID)
    integration = await scm_webhook_service.find_integration(
        db, ScmProvider.GITHUB, repo_full_name
    )
    if integration is None:
        logger.info("Webhook dla nieznanego repozytorium %s — ignoruję", repo_full_name)
        return WebhookAckResponse(status="ignored", detail="Repozytorium nie jest podłączone")

    secret = (
        decrypt_token(integration.webhook_secret_encrypted, integration.tenant_id)
        if integration.webhook_secret_encrypted
        else None
    )
    if not secret or not github_service.verify_webhook_signature(
        raw_body, x_hub_signature_256, secret
    ):
        await _set_rls_tenant(db, integration.tenant_id)
        await log_action(
            db,
            tenant_id=integration.tenant_id,
            user_id=None,
            action="integration.github.webhook_rejected",
            resource_type="scm_integration",
            resource_id=integration.id,
            changes={"repo": repo_full_name, "reason": "invalid_signature", "event": x_github_event},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        logger.warning("Odrzucony webhook GitHuba dla %s — zły podpis", repo_full_name)
        # 401 świadomie: fałszywy podpis to nie jest dostawa, którą chcemy
        # potwierdzać, a GitHub pokaże to wprost w historii dostaw.
        raise _webhook_unauthorized()

    parsed = scm_webhook_service.parse_github_event(x_github_event or "", payload)
    if parsed is None:
        return WebhookAckResponse(status="ignored", detail=f"Zdarzenie '{x_github_event}' nieobsługiwane")

    await _set_rls_tenant(db, integration.tenant_id)
    event = await scm_webhook_service.record_event(db, integration, parsed)
    await db.commit()

    if event.status == ScmEventStatus.SKIPPED:
        return WebhookAckResponse(status="skipped", event_id=event.id, detail=parsed.skip_reason)

    task_id = scm_webhook_service.dispatch_event_analysis(event.id)
    if task_id:
        event.task_id = task_id
        await db.commit()
    return WebhookAckResponse(status="accepted", event_id=event.id, task_id=task_id)


def _webhook_unauthorized():
    from app.core.exceptions import AuthError

    return AuthError("Nieprawidłowy podpis webhooka")


# ── GitLab: OAuth (Story 8.2, AC1) ──────────────────────────────────────────


@router.get("/gitlab/authorize")
async def gitlab_authorize(
    gitlab_url: str | None = Query(None, description="Adres instancji GitLab (domyślnie gitlab.com)"),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    """URL autoryzacji wskazanej instancji GitLab (AC1).

    Adres instancji wędruje w ``state``, bo callback musi wiedzieć, do którego
    GitLaba wysłać żądanie wymiany kodu — ta sama aplikacja OAuth obsługuje
    gitlab.com i instancje self-hosted.
    """
    if not gitlab_service.is_configured():
        raise ValidationError(
            "Integracja z GitLab nie jest skonfigurowana — uzupełnij GITLAB_CLIENT_ID i GITLAB_CLIENT_SECRET"
        )

    instance_url = gitlab_service.normalize_gitlab_url(gitlab_url)
    state = secrets.token_urlsafe(32)
    await redis.set(
        _state_key(state),
        json.dumps(
            {
                "user_id": str(current_user.id),
                "tenant_id": str(tenant_id),
                "gitlab_url": instance_url,
            }
        ),
        ex=_STATE_TTL_SECONDS,
    )
    return {"authorization_url": gitlab_service.get_authorization_url(instance_url, state)}


@router.get("/gitlab/callback")
async def gitlab_callback(
    code: str = Query(...),
    state: str = Query(...),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Odbiera powrót z GitLaba i odsyła użytkownika na frontend (AC1)."""
    frontend = get_settings().frontend_base_url.rstrip("/")
    target = f"{frontend}/settings/integrations/gitlab"

    raw_state = await redis.get(_state_key(state))
    if not raw_state:
        return RedirectResponse(f"{target}?error=invalid_state", status_code=302)
    await redis.delete(_state_key(state))  # jednorazowy — chroni przed replayem

    context = json.loads(raw_state)
    instance_url = context.get("gitlab_url") or gitlab_service.default_gitlab_url()

    try:
        token_payload = await gitlab_service.exchange_code_for_token(instance_url, code)
    except Exception as exc:
        logger.warning("Wymiana kodu GitLaba nie powiodła się: %s", exc)
        return RedirectResponse(f"{target}?error=token_exchange", status_code=302)

    user_id = uuid.UUID(context["user_id"])
    await redis.set(
        _token_key(ScmProvider.GITLAB, user_id),
        token_payload["access_token"],
        ex=_TOKEN_TTL_SECONDS,
    )
    # Adres instancji trzymamy obok tokenu — kolejne kroki (lista projektów,
    # rejestracja webhooka) muszą wiedzieć, z którym GitLabem rozmawiają.
    await redis.set(
        f"gitlab:instance_url:{user_id}", instance_url, ex=_TOKEN_TTL_SECONDS
    )
    return RedirectResponse(f"{target}?connected=1", status_code=302)


async def _resolve_gitlab_instance(
    db: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    gitlab_url: str | None = None,
) -> str:
    """Adres instancji: z żądania, ze świeżej autoryzacji albo z zapisanej integracji."""
    if gitlab_url:
        return gitlab_service.normalize_gitlab_url(gitlab_url)

    cached = await redis.get(f"gitlab:instance_url:{user_id}")
    if cached:
        return cached if isinstance(cached, str) else cached.decode()

    existing = await _list_active(db, tenant_id, ScmProvider.GITLAB)
    if existing:
        stored = (existing[0].config or {}).get("gitlab_url")
        if stored:
            return gitlab_service.normalize_gitlab_url(stored)
    return gitlab_service.default_gitlab_url()


# ── GitLab: projekty (AC1, AC2, AC6) ────────────────────────────────────────


@router.get("/gitlab/available-projects", response_model=list[GitLabProjectOption])
async def list_available_gitlab_projects(
    gitlab_url: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[GitLabProjectOption]:
    """Projekty widoczne dla autoryzacji GitLab, z oznaczeniem podłączonych (AC1)."""
    instance_url = await _resolve_gitlab_instance(db, redis, current_user.id, tenant_id, gitlab_url)
    access_token = await _resolve_access_token(
        db, redis, current_user.id, tenant_id, ScmProvider.GITLAB
    )
    projects = await gitlab_service.get_user_projects(access_token, instance_url)

    connected = {i.repo_full_name for i in await _list_active(db, tenant_id, ScmProvider.GITLAB)}

    return [
        GitLabProjectOption(
            project_id=project["id"],
            path_with_namespace=project["path_with_namespace"],
            name=project.get("name") or project["path_with_namespace"],
            visibility=project.get("visibility") or "private",
            default_branch=project.get("default_branch") or "main",
            web_url=project.get("web_url") or "",
            http_url_to_repo=project.get("http_url_to_repo") or "",
            connected=project["path_with_namespace"] in connected,
        )
        for project in projects
    ]


@router.get("/gitlab/projects", response_model=ScmIntegrationListResponse)
async def list_connected_gitlab_projects(
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> ScmIntegrationListResponse:
    """Podłączone projekty GitLab wraz ze statusem webhooka (AC1/AC6)."""
    items = [_to_response(i) for i in await _list_active(db, tenant_id, ScmProvider.GITLAB)]
    return ScmIntegrationListResponse(
        items=items,
        total=len(items),
        provider_configured=gitlab_service.is_configured(),
    )


@router.post(
    "/gitlab/projects",
    response_model=ScmIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_gitlab_project(
    body: ConnectGitLabProjectRequest,
    request: Request,
    gitlab_url: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ScmIntegrationResponse:
    """Podłącza projekt GitLab i rejestruje na nim webhook (AC1/AC2)."""
    instance_url = await _resolve_gitlab_instance(db, redis, current_user.id, tenant_id, gitlab_url)
    access_token = await _resolve_access_token(
        db, redis, current_user.id, tenant_id, ScmProvider.GITLAB
    )

    projects = await gitlab_service.get_user_projects(access_token, instance_url)
    project = next((p for p in projects if p["id"] == body.project_id), None)
    if project is None:
        raise NotFoundError("Projekt nie jest dostępny dla tej autoryzacji GitLab")

    path_with_namespace = project["path_with_namespace"]
    existing = await _find_by_repo_any_tenant(db, ScmProvider.GITLAB, path_with_namespace)
    await _set_rls_tenant(db, tenant_id)

    if existing is not None and existing.is_active:
        if existing.tenant_id != tenant_id:
            raise ConflictError("Ten projekt jest już podłączony do innej firmy w TestGEN")
        raise ConflictError("Ten projekt jest już podłączony")

    webhook_secret = gitlab_service.generate_webhook_secret()
    hook = await gitlab_service.register_webhook(
        access_token,
        instance_url,
        body.project_id,
        _webhook_url(ScmProvider.GITLAB),
        webhook_secret,
    )

    if existing is not None:  # reaktywacja wcześniej odłączonego projektu
        integration = existing
        integration.tenant_id = tenant_id
        integration.user_id = current_user.id
        integration.is_active = True
    else:
        integration = ScmIntegration(
            tenant_id=tenant_id,
            user_id=current_user.id,
            provider=ScmProvider.GITLAB,
            repo_full_name=path_with_namespace,
            is_active=True,
        )
        db.add(integration)

    integration.repo_url = project.get("http_url_to_repo") or project.get("web_url") or ""
    integration.default_branch = project.get("default_branch") or "main"
    integration.access_token_encrypted = encrypt_token(access_token, tenant_id)
    integration.webhook_secret_encrypted = encrypt_token(webhook_secret, tenant_id)
    integration.hook_id = str(hook.get("id")) if hook.get("id") is not None else None
    # ``gitlab_project_id`` i adres instancji są niezbędne do wszystkich
    # dalszych wywołań API — GitLab nie adresuje projektów ścieżką.
    integration.config = {
        "gitlab_url": instance_url,
        "gitlab_project_id": body.project_id,
        "visibility": project.get("visibility"),
    }
    await db.flush()

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.gitlab.connected",
        resource_type="scm_integration",
        resource_id=integration.id,
        changes={
            "project": path_with_namespace,
            "gitlab_url": instance_url,
            "hook_id": integration.hook_id,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(integration)
    return _to_response(integration)


@router.delete("/gitlab/projects/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_gitlab_project(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Odłącza projekt i kasuje webhook u dostawcy (AC6)."""
    integration = (
        await db.execute(
            select(ScmIntegration).where(
                ScmIntegration.id == integration_id,
                ScmIntegration.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("Integracja nie została znaleziona")

    config = integration.config or {}
    project_id = config.get("gitlab_project_id")
    if integration.hook_id and project_id:
        try:
            access_token = decrypt_token(integration.access_token_encrypted, tenant_id)
            await gitlab_service.delete_webhook(
                access_token,
                config.get("gitlab_url") or gitlab_service.default_gitlab_url(),
                int(project_id),
                integration.hook_id,
            )
        except Exception as exc:
            # Jak przy GitHubie: nieudane sprzątanie po stronie dostawcy nie może
            # zostawić martwej integracji na naszej liście na zawsze.
            logger.warning("Nie udało się usunąć webhooka na GitLabie: %s", exc)

    integration.is_active = False
    integration.hook_id = None
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.gitlab.disconnected",
        resource_type="scm_integration",
        resource_id=integration.id,
        changes={"project": integration.repo_full_name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/gitlab/events", response_model=list[IntegrationEventResponse])
async def list_gitlab_events(
    integration_id: uuid.UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationEventResponse]:
    """Ostatnie zdarzenia z webhooków GitLaba — domyślnie 10 (AC6)."""
    return await _recent_events(db, tenant_id, ScmProvider.GITLAB, integration_id, limit)


# ── GitLab: webhook (bez uwierzytelnienia — bramą jest X-Gitlab-Token) ───────


@router.post("/gitlab/webhook", response_model=WebhookAckResponse)
async def gitlab_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gitlab_event: str | None = Header(None),
    x_gitlab_token: str | None = Header(None),
) -> WebhookAckResponse:
    """Przyjmuje zdarzenie z GitLaba, weryfikuje token i kolejkuje analizę (AC3-AC5).

    GitLab nie podpisuje ciała — odsyła ten sam sekret, który zapisaliśmy przy
    rejestracji webhooka, więc weryfikacja to stałoczasowe porównanie sekretów.
    """
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise ValidationError("Nieprawidłowy JSON w ciele webhooka") from None

    path_with_namespace = (payload.get("project") or {}).get("path_with_namespace")
    if not path_with_namespace:
        return WebhookAckResponse(status="ignored", detail="Payload bez projektu")

    await _set_rls_tenant(db, NIL_UUID)
    integration = await scm_webhook_service.find_integration(
        db, ScmProvider.GITLAB, path_with_namespace
    )
    if integration is None:
        logger.info("Webhook dla niepodłączonego projektu %s — ignoruję", path_with_namespace)
        return WebhookAckResponse(status="ignored", detail="Projekt nie jest podłączony")

    secret = (
        decrypt_token(integration.webhook_secret_encrypted, integration.tenant_id)
        if integration.webhook_secret_encrypted
        else None
    )
    if not secret or not gitlab_service.verify_webhook_token(x_gitlab_token, secret):
        await _set_rls_tenant(db, integration.tenant_id)
        await log_action(
            db,
            tenant_id=integration.tenant_id,
            user_id=None,
            action="integration.gitlab.webhook_rejected",
            resource_type="scm_integration",
            resource_id=integration.id,
            changes={
                "project": path_with_namespace,
                "reason": "invalid_token",
                "event": x_gitlab_event,
            },
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
        logger.warning("Odrzucony webhook GitLaba dla %s — zły token", path_with_namespace)
        raise _webhook_unauthorized()

    parsed = scm_webhook_service.parse_gitlab_event(x_gitlab_event or "", payload)
    if parsed is None:
        return WebhookAckResponse(
            status="ignored", detail=f"Zdarzenie '{x_gitlab_event}' nieobsługiwane"
        )

    await _set_rls_tenant(db, integration.tenant_id)
    event = await scm_webhook_service.record_event(db, integration, parsed)
    await db.commit()

    if event.status == ScmEventStatus.SKIPPED:
        return WebhookAckResponse(status="skipped", event_id=event.id, detail=parsed.skip_reason)

    task_id = scm_webhook_service.dispatch_event_analysis(event.id)
    if task_id:
        event.task_id = task_id
        await db.commit()
    return WebhookAckResponse(status="accepted", event_id=event.id, task_id=task_id)


# ── konfiguracja status checków (Story 8.3, AC3/AC5/AC6) ────────────────────


def _status_config_response(integration: ScmIntegration) -> StatusCheckConfigResponse:
    config = integration.config or {}
    return StatusCheckConfigResponse(
        integration_id=integration.id,
        severity_threshold=normalize_threshold(config.get("severity_threshold")),
        post_comment=bool(config.get("post_comment", True)),
        fail_on_threshold=bool(config.get("fail_on_threshold", True)),
        status_context=STATUS_CONTEXT,
    )


async def _owned_integration(
    db: AsyncSession, integration_id: uuid.UUID, tenant_id: uuid.UUID
) -> ScmIntegration:
    integration = (
        await db.execute(
            select(ScmIntegration).where(
                ScmIntegration.id == integration_id,
                ScmIntegration.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("Integracja nie została znaleziona")
    return integration


@router.get("/{integration_id}/config", response_model=StatusCheckConfigResponse)
async def get_status_check_config(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> StatusCheckConfigResponse:
    """Aktualne ustawienia status checka wraz z nazwą do branch protection (AC6)."""
    return _status_config_response(await _owned_integration(db, integration_id, tenant_id))


@router.put("/{integration_id}/config", response_model=StatusCheckConfigResponse)
async def update_status_check_config(
    integration_id: uuid.UUID,
    body: StatusCheckConfigRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> StatusCheckConfigResponse:
    """Zmienia próg blokowania i komentarze (AC3/AC5/AC6).

    Nadpisujemy wyłącznie klucze status checka — ``config`` niesie też dane
    połączenia (adres instancji i identyfikator projektu GitLaba), których
    nie wolno zgubić.
    """
    integration = await _owned_integration(db, integration_id, tenant_id)

    config = dict(integration.config or {})
    config.update(
        {
            "severity_threshold": body.severity_threshold,
            "post_comment": body.post_comment,
            "fail_on_threshold": body.fail_on_threshold,
        }
    )
    integration.config = config

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.status_check.configured",
        resource_type="scm_integration",
        resource_id=integration.id,
        changes={
            "repo": integration.repo_full_name,
            "severity_threshold": body.severity_threshold,
            "post_comment": body.post_comment,
            "fail_on_threshold": body.fail_on_threshold,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(integration)
    return _status_config_response(integration)
