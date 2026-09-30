"""API testy generatora CI/CD — Story 8.4 (AC1-AC6; Task 5.3).

Osobna sekcja pilnuje tego, co ta story naprawiła: klucz API (Story 8.6)
uwierzytelnia zwykłe endpointy, ale nie wystarcza do zakładania kolejnych
kluczy. Bez pierwszego generowane pipeline'y dostawałyby 401; bez drugiego
klucz full-access mógłby wyprodukować sobie następny.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.project import Project, ProjectStatus
from tests.factories import make_user

BASE = "/api/v1/projects"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _override(app, db) -> tuple[uuid.UUID, uuid.UUID]:
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    user = make_user(email="owner@a.com", name="Owner")
    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id
    project_id = uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = "owner"
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id, project_id


def _project(project_id, tenant_id) -> Project:
    return Project(
        id=project_id,
        tenant_id=tenant_id,
        name="Projekt",
        status=ProjectStatus.ACTIVE,
        is_deleted=False,
        created_at=datetime.now(UTC),
    )


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


# ── katalog platform (AC5/AC6) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lista_platform_zawiera_cztery_ci(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/templates")

    assert resp.status_code == 200
    body = resp.json()
    assert {p["platform"] for p in body["platforms"]} == {
        "jenkins",
        "github_actions",
        "azure_devops",
        "gitlab_ci",
    }
    assert body["api_key_variable"] == "TESTGEN_API_KEY"
    assert body["available_thresholds"] == ["critical", "high", "medium"]
    assert "code_analysis" in body["available_modules"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lista_platform_dla_cudzego_projektu_to_404(app, client):
    db = _db()
    _override(app, db)
    db.execute.return_value = _scalar(None)

    resp = await client.get(f"{BASE}/{uuid.uuid4()}/ci-cd/templates")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ── generowanie (AC1-AC4, AC6) ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("platform", "filename"),
    [
        ("jenkins", "Jenkinsfile"),
        ("github_actions", ".github/workflows/testgen.yml"),
        ("azure_devops", "azure-pipelines.yml"),
        ("gitlab_ci", ".gitlab-ci.yml"),
    ],
)
@pytest.mark.asyncio
async def test_generowanie_kazdej_platformy(app, client, platform, filename):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate", json={"platform": platform}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["platform"] == platform
    assert body["filename"] == filename
    assert str(project_id) in body["content"]
    assert body["secret_hint"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wygenerowany_workflow_jest_poprawnym_yamlem(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate",
        json={"platform": "github_actions", "modules": ["code_analysis", "security_scan"]},
    )

    parsed = yaml.safe_load(resp.json()["content"])
    assert "jobs" in parsed
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_parametry_trafiaja_do_wygenerowanego_pliku(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate",
        json={
            "platform": "gitlab_ci",
            "severity_threshold": "medium",
            "modules": ["security_scan"],
            "engine_mode": "hybrid",
            "timeout_minutes": 10,
        },
    )

    content = resp.json()["content"]
    assert "threshold=medium" in content
    assert '"engine_mode": "hybrid"' in content
    assert '"modules": ["security_scan"]' in content
    assert "timeout: 10 minutes" in content
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nieznana_platforma_to_422(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate", json={"platform": "travis"}
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_niedozwolony_prog_to_422(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate",
        json={"platform": "jenkins", "severity_threshold": "low"},
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_timeout_poza_zakresem_to_422(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.return_value = _scalar(_project(project_id, tenant_id))

    resp = await client.post(
        f"{BASE}/{project_id}/ci-cd/generate",
        json={"platform": "jenkins", "timeout_minutes": 500},
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


# ── werdykt bramki (AC1-AC4) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_podsumowanie_bez_znalezisk_przepuszcza_build(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.side_effect = [_scalar(_project(project_id, tenant_id)), _scalars([]), _scalars([])]

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["should_fail"] is False
    assert body["state"] == "success"
    assert body["total"] == 0
    assert body["threshold"] == "critical"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_podsumowanie_z_krytycznym_przerywa_build(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    findings = [
        _Row(severity="critical", vulnerability_type="SQLi", file_path="db.py", line_start=1)
    ]
    db.execute.side_effect = [
        _scalar(_project(project_id, tenant_id)),
        _scalars(findings),
        _scalars([]),
    ]

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["should_fail"] is True
    assert body["blocking"] == 1
    assert body["counts"]["critical"] == 1
    assert "krytyczny" in body["description"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_prog_z_parametru_jest_respektowany(app, client):
    """Znalezisko 'high' nie blokuje przy progu critical, ale blokuje przy high."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    findings = [_Row(severity="high", vulnerability_type="XSS", file_path="v.py", line_start=2)]
    db.execute.side_effect = [
        _scalar(_project(project_id, tenant_id)),
        _scalars(findings),
        _scalars([]),
    ]

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/summary", params={"threshold": "high"})

    assert resp.json()["should_fail"] is True
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_niepoprawny_prog_spada_na_domyslny(app, client):
    """Pipeline nie może paść przez literówkę w parametrze — bierzemy default."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    db.execute.side_effect = [_scalar(_project(project_id, tenant_id)), _scalars([]), _scalars([])]

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/summary", params={"threshold": "bardzo-zly"})

    assert resp.status_code == 200
    assert resp.json()["threshold"] == "critical"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bledy_kodu_tez_wliczane_do_werdyktu(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    code_errors = [_Row(severity="critical", message="Błąd składni", file_path="a.py", line_start=1)]
    db.execute.side_effect = [
        _scalar(_project(project_id, tenant_id)),
        _scalars([]),
        _scalars(code_errors),
    ]

    resp = await client.get(f"{BASE}/{project_id}/ci-cd/summary")

    assert resp.json()["should_fail"] is True
    app.dependency_overrides.clear()


# ── uwierzytelnianie kluczem API (naprawa luki z 8.6) ────────────────────────


@pytest.mark.asyncio
async def test_klucz_api_uwierzytelnia_zwykly_endpoint():
    """Bez tego wygenerowane pipeline'y dostawałyby 401 na każdym kroku."""
    from types import SimpleNamespace

    from app.core.dependencies import get_current_user

    raw_key = "tgn_" + "a" * 64
    user = make_user(email="ci@a.com", name="CI")
    request = SimpleNamespace(state=SimpleNamespace(), method="GET")

    with patch(
        "app.core.api_key_auth.authenticate_api_key", AsyncMock(return_value=user)
    ) as auth:
        result = await get_current_user(
            request=request,
            db=AsyncMock(),
            redis=AsyncMock(),
            authorization=f"Bearer {raw_key}",
            access_token=None,
        )

    assert result is user
    auth.assert_awaited_once()
    assert auth.await_args.args[1] == raw_key


@pytest.mark.asyncio
async def test_token_bez_prefiksu_nie_idzie_sciezka_klucza():
    """Token bez ``tgn_`` musi trafić do dekodowania JWT, nie do walidacji klucza.

    Samego dekodowania nie sprawdzamy — wymaga kluczy RSA, których to
    środowisko nie ma; istotne jest, że gałąź kluczy API nie zostaje wybrana.
    """
    from contextlib import suppress
    from types import SimpleNamespace

    from app.core.dependencies import get_current_user

    request = SimpleNamespace(state=SimpleNamespace(), method="GET")

    with (
        patch("app.core.api_key_auth.authenticate_api_key", AsyncMock()) as auth,
        suppress(Exception),
    ):
        await get_current_user(
                request=request,
                db=AsyncMock(),
                redis=AsyncMock(),
            authorization="Bearer eyJhbGciOiJSUzI1NiJ9.a.b",
            access_token=None,
        )

    auth.assert_not_awaited()


def test_require_session_odrzuca_klucz_api():
    """Klucz full-access nie może wyprodukować sobie kolejnego klucza."""
    from types import SimpleNamespace

    from app.core.dependencies import require_session
    from app.core.exceptions import ForbiddenError

    user = make_user(email="ci@a.com", name="CI")
    request = SimpleNamespace(state=SimpleNamespace(api_key_id=uuid.uuid4()))

    with pytest.raises(ForbiddenError, match="sesji"):
        require_session(request, user)


def test_require_session_przepuszcza_sesje_jwt():
    from types import SimpleNamespace

    from app.core.dependencies import require_session

    user = make_user(email="owner@a.com", name="Owner")
    request = SimpleNamespace(state=SimpleNamespace())

    assert require_session(request, user) is user
