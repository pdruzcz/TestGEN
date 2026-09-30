"""Generator konfiguracji CI/CD — Epic 8, Story 8.4.

Wygenerowane pliki mają działać po wklejeniu do repozytorium, więc wołają
realne endpointy TestGEN i uwierzytelniają się kluczem API ze Story 8.6
(``Authorization: Bearer tgn_…``). Każdy pipeline przechodzi tę samą ścieżkę:

1. spakowanie katalogu roboczego do ZIP-a (upload przyjmuje archiwa,
   Story 1.6-zakańczenie rozpakowuje je po stronie serwera),
2. ``POST /projects/{id}/upload``,
3. ``POST /projects/{id}/analyze`` → ``task_id``,
4. odpytywanie ``GET /tasks/{task_id}`` aż do zakończenia,
5. ``GET /projects/{id}/ci-cd/summary`` → decyzja o przerwaniu builda.

Punkt 5 jest osobnym endpointem, a nie liczeniem znalezisk w basha: próg
musi znaczyć to samo co w status checkach na PR (Story 8.3), a jedyny
sposób, żeby nie rozjechały się z czasem, to wspólne źródło decyzji.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.config import get_settings
from app.core.exceptions import ValidationError

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Szablony konfiguracji to nie HTML — autoescape zepsułby cudzysłowy w YAML-u
# i w Groovym. Dane wejściowe są walidowane enumami, nie pochodzą od anonimów.
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    undefined=StrictUndefined,  # literówka w nazwie zmiennej ma wysypać test, nie pipeline klienta
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


class CicdPlatform(StrEnum):
    JENKINS = "jenkins"
    GITHUB_ACTIONS = "github_actions"
    AZURE_DEVOPS = "azure_devops"
    GITLAB_CI = "gitlab_ci"


ANALYSIS_MODULES: tuple[str, ...] = (
    "code_analysis",
    "doc_analysis",
    "security_scan",
    "uml_analysis",
)
ENGINE_MODES: tuple[str, ...] = ("native", "llm", "hybrid")
SEVERITY_THRESHOLDS: tuple[str, ...] = ("critical", "high", "medium")

MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 180

# Nazwa zmiennej/credentiala z kluczem API — jedna dla wszystkich platform,
# żeby instrukcja dla użytkownika brzmiała tak samo niezależnie od CI.
API_KEY_VARIABLE = "TESTGEN_API_KEY"

_PLATFORM_META: dict[CicdPlatform, dict[str, str]] = {
    CicdPlatform.JENKINS: {
        "filename": "Jenkinsfile",
        "template": "jenkinsfile.j2",
        "language": "groovy",
        "label": "Jenkins",
        "description": "Deklaratywny Jenkinsfile — klucz API z Credentials (Secret text).",
        "secret_hint": (
            "Dodaj w Jenkins → Manage Credentials poświadczenie typu „Secret text” "
            f"o identyfikatorze {API_KEY_VARIABLE.lower()}."
        ),
    },
    CicdPlatform.GITHUB_ACTIONS: {
        "filename": ".github/workflows/testgen.yml",
        "template": "github_actions.yml.j2",
        "language": "yaml",
        "label": "GitHub Actions",
        "description": "Workflow uruchamiany przy push i pull request.",
        "secret_hint": (
            f"Dodaj sekret repozytorium {API_KEY_VARIABLE} w Settings → Secrets and variables → Actions."
        ),
    },
    CicdPlatform.AZURE_DEVOPS: {
        "filename": "azure-pipelines.yml",
        "template": "azure_pipelines.yml.j2",
        "language": "yaml",
        "label": "Azure DevOps",
        "description": "Pipeline YAML — klucz API ze zmiennej grupy lub zmiennej sekretnej.",
        "secret_hint": (
            f"Dodaj zmienną sekretną {API_KEY_VARIABLE} w Pipelines → Library → Variable groups."
        ),
    },
    CicdPlatform.GITLAB_CI: {
        "filename": ".gitlab-ci.yml",
        "template": "gitlab_ci.yml.j2",
        "language": "yaml",
        "label": "GitLab CI",
        "description": "Etap test z artefaktem zawierającym podsumowanie analizy.",
        "secret_hint": (
            f"Dodaj zmienną {API_KEY_VARIABLE} (maskowaną) w Settings → CI/CD → Variables."
        ),
    },
}


@dataclass
class CicdParams:
    """Parametry generowanej konfiguracji (AC6)."""

    project_id: str
    platform: CicdPlatform = CicdPlatform.GITHUB_ACTIONS
    severity_threshold: str = "critical"
    modules: list[str] = field(default_factory=lambda: ["code_analysis"])
    engine_mode: str = "native"
    timeout_minutes: int = 30
    api_url: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.platform, str):
            self.platform = CicdPlatform(self.platform)
        if self.severity_threshold not in SEVERITY_THRESHOLDS:
            raise ValidationError(
                f"Nieprawidłowy próg: {self.severity_threshold}. "
                f"Dozwolone: {', '.join(SEVERITY_THRESHOLDS)}"
            )
        if self.engine_mode not in ENGINE_MODES:
            raise ValidationError(
                f"Nieprawidłowy tryb silnika: {self.engine_mode}. Dozwolone: {', '.join(ENGINE_MODES)}"
            )
        unknown = [m for m in self.modules if m not in ANALYSIS_MODULES]
        if unknown:
            raise ValidationError(f"Nieznane moduły analizy: {', '.join(sorted(unknown))}")
        if not self.modules:
            raise ValidationError("Wybierz co najmniej jeden moduł analizy")
        if not (MIN_TIMEOUT_MINUTES <= self.timeout_minutes <= MAX_TIMEOUT_MINUTES):
            raise ValidationError(
                f"Timeout musi mieścić się w zakresie {MIN_TIMEOUT_MINUTES}-{MAX_TIMEOUT_MINUTES} minut"
            )
        if self.api_url is None:
            self.api_url = get_settings().api_public_base_url.rstrip("/")
        else:
            self.api_url = self.api_url.rstrip("/")

    @property
    def poll_attempts(self) -> int:
        """Ile razy odpytać status przy odstępie 10 s, żeby zmieścić się w timeoucie."""
        return max(1, self.timeout_minutes * 6)


def list_platforms() -> list[dict[str, str]]:
    """Katalog platform dla frontendu (AC5/AC6)."""
    return [
        {
            "platform": platform.value,
            "label": meta["label"],
            "filename": meta["filename"],
            "language": meta["language"],
            "description": meta["description"],
            "secret_hint": meta["secret_hint"],
        }
        for platform, meta in _PLATFORM_META.items()
    ]


def _render(params: CicdParams) -> str:
    meta = _PLATFORM_META[params.platform]
    template = _jinja_env.get_template(meta["template"])
    return template.render(
        api_url=params.api_url,
        project_id=params.project_id,
        severity_threshold=params.severity_threshold,
        modules=params.modules,
        modules_json=", ".join(f'\\"{m}\\"' for m in params.modules),
        engine_mode=params.engine_mode,
        timeout_minutes=params.timeout_minutes,
        poll_attempts=params.poll_attempts,
        api_key_variable=API_KEY_VARIABLE,
    )


def generate_jenkinsfile(params: CicdParams) -> str:
    return _render(CicdParams(**{**params.__dict__, "platform": CicdPlatform.JENKINS}))


def generate_github_actions(params: CicdParams) -> str:
    return _render(CicdParams(**{**params.__dict__, "platform": CicdPlatform.GITHUB_ACTIONS}))


def generate_azure_pipelines(params: CicdParams) -> str:
    return _render(CicdParams(**{**params.__dict__, "platform": CicdPlatform.AZURE_DEVOPS}))


def generate_gitlab_ci(params: CicdParams) -> str:
    return _render(CicdParams(**{**params.__dict__, "platform": CicdPlatform.GITLAB_CI}))


def generate(params: CicdParams) -> dict[str, str]:
    """Zwraca ``{platform, filename, language, content, secret_hint}`` (AC1-AC4)."""
    meta = _PLATFORM_META[params.platform]
    return {
        "platform": params.platform.value,
        "filename": meta["filename"],
        "language": meta["language"],
        "secret_hint": meta["secret_hint"],
        "content": _render(params),
    }
