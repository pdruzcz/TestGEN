"""Testy generatora konfiguracji CI/CD — Story 8.4 (AC1-AC4, AC6; Task 5.1/5.2).

Wygenerowany plik ma działać po wklejeniu do repozytorium, więc testy
sprawdzają trzy rzeczy naraz: że to poprawny YAML/Groovy, że woła realne
endpointy TestGEN i że parametry faktycznie trafiają do treści — a nie że
funkcja „coś zwróciła".
"""

import pytest
import yaml

from app.core.exceptions import ValidationError
from app.services.integrations.cicd_generator import (
    ANALYSIS_MODULES,
    API_KEY_VARIABLE,
    ENGINE_MODES,
    SEVERITY_THRESHOLDS,
    CicdParams,
    CicdPlatform,
    generate,
    generate_azure_pipelines,
    generate_github_actions,
    generate_gitlab_ci,
    generate_jenkinsfile,
    list_platforms,
)

PROJECT_ID = "11111111-1111-1111-1111-111111111111"
API_URL = "https://api.testgen.io"

# Platformy z konfiguracją w YAML-u — Jenkinsfile jest Groovym.
YAML_PLATFORMS = (
    CicdPlatform.GITHUB_ACTIONS,
    CicdPlatform.AZURE_DEVOPS,
    CicdPlatform.GITLAB_CI,
)


def _params(**overrides) -> CicdParams:
    defaults = {"project_id": PROJECT_ID, "api_url": API_URL}
    defaults.update(overrides)
    return CicdParams(**defaults)


def _content(platform: CicdPlatform, **overrides) -> str:
    return generate(_params(platform=platform, **overrides))["content"]


# ── katalog platform (AC5/AC6) ───────────────────────────────────────────────


def test_katalog_zawiera_cztery_platformy():
    platforms = list_platforms()

    assert {p["platform"] for p in platforms} == {p.value for p in CicdPlatform}
    assert len(platforms) == 4


def test_katalog_podaje_nazwe_pliku_i_jezyk():
    by_platform = {p["platform"]: p for p in list_platforms()}

    assert by_platform["jenkins"]["filename"] == "Jenkinsfile"
    assert by_platform["jenkins"]["language"] == "groovy"
    assert by_platform["github_actions"]["filename"] == ".github/workflows/testgen.yml"
    assert by_platform["azure_devops"]["filename"] == "azure-pipelines.yml"
    assert by_platform["gitlab_ci"]["filename"] == ".gitlab-ci.yml"
    assert all(p["language"] == "yaml" for p in list_platforms() if p["platform"] != "jenkins")


def test_katalog_wyjasnia_jak_dodac_klucz_w_kazdej_platformie():
    """Instrukcja różni się per CI — to najczęstsze miejsce potknięcia."""
    for platform in list_platforms():
        assert platform["secret_hint"]
        assert len(platform["secret_hint"]) > 30


# ── walidacja parametrów (AC6) ───────────────────────────────────────────────


def test_domyslne_parametry():
    params = _params()

    assert params.platform == CicdPlatform.GITHUB_ACTIONS
    assert params.severity_threshold == "critical"
    assert params.modules == ["code_analysis"]
    assert params.engine_mode == "native"
    assert params.timeout_minutes == 30


def test_platforma_przyjmowana_takze_jako_tekst():
    assert _params(platform="jenkins").platform == CicdPlatform.JENKINS


@pytest.mark.parametrize("threshold", SEVERITY_THRESHOLDS)
def test_dozwolone_progi(threshold):
    assert _params(severity_threshold=threshold).severity_threshold == threshold


@pytest.mark.parametrize("bad", ["low", "info", "", "CRITICAL"])
def test_niedozwolony_prog_odrzucony(bad):
    with pytest.raises(ValidationError, match="próg"):
        _params(severity_threshold=bad)


@pytest.mark.parametrize("mode", ENGINE_MODES)
def test_dozwolone_tryby_silnika(mode):
    assert _params(engine_mode=mode).engine_mode == mode


def test_nieznany_tryb_silnika_odrzucony():
    with pytest.raises(ValidationError, match="tryb silnika"):
        _params(engine_mode="magiczny")


def test_nieznany_modul_odrzucony():
    with pytest.raises(ValidationError, match="moduły"):
        _params(modules=["code_analysis", "wymyslony_modul"])


def test_pusta_lista_modulow_odrzucona():
    with pytest.raises(ValidationError, match="co najmniej jeden"):
        _params(modules=[])


@pytest.mark.parametrize("bad", [0, -5, 181, 1000])
def test_timeout_poza_zakresem_odrzucony(bad):
    with pytest.raises(ValidationError, match="Timeout"):
        _params(timeout_minutes=bad)


def test_liczba_prob_odpytywania_wynika_z_timeoutu():
    """Odstęp 10 s — sześć prób na minutę."""
    assert _params(timeout_minutes=30).poll_attempts == 180
    assert _params(timeout_minutes=1).poll_attempts == 6


def test_koncowy_ukosnik_adresu_api_jest_obcinany():
    assert _params(api_url="https://api.testgen.io/").api_url == "https://api.testgen.io"


# ── poprawność składni (Task 5.2) ────────────────────────────────────────────


@pytest.mark.parametrize("platform", YAML_PLATFORMS)
def test_wygenerowany_yaml_jest_parsowalny(platform):
    yaml.safe_load(_content(platform))


@pytest.mark.parametrize("platform", YAML_PLATFORMS)
def test_yaml_parsuje_sie_dla_wszystkich_kombinacji_modulow(platform):
    content = _content(platform, modules=list(ANALYSIS_MODULES))
    yaml.safe_load(content)


def test_jenkinsfile_ma_zbilansowane_nawiasy_klamrowe():
    """Groovy nie ma parsera w tych testach — sprawdzamy strukturę pipeline'u."""
    content = _content(CicdPlatform.JENKINS)

    assert content.count("{") == content.count("}")
    assert "pipeline {" in content
    assert "stages {" in content
    assert "post {" in content


def test_github_actions_zachowuje_wlasne_wyrazenia():
    """``${{ secrets.X }}`` to składnia GitHuba — Jinja nie może jej zjeść."""
    content = _content(CicdPlatform.GITHUB_ACTIONS)

    assert "${{ secrets.TESTGEN_API_KEY }}" in content
    assert "${{ steps.analyze.outputs.task_id }}" in content
    # Żadnych niepodstawionych znaczników Jinja
    assert "{%" not in content
    assert "{#" not in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_brak_niepodstawionych_zmiennych(platform):
    content = _content(platform)
    assert "{{" not in content.replace("${{", "").replace("{{ '", "")


# ── treść: realne endpointy (AC1-AC4) ────────────────────────────────────────


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_kazda_konfiguracja_przechodzi_pelna_sciezke(platform):
    """Upload → analiza → odpytywanie → próg. Brak któregokolwiek kroku
    czyniłby konfigurację bezużyteczną.

    Adres i identyfikator projektu wchodzą przez zmienne środowiskowe, więc
    sprawdzamy ścieżki endpointów osobno od wartości tych zmiennych.
    """
    content = _content(platform)

    assert "/api/v1/projects/" in content
    assert "/upload" in content
    assert "/analyze" in content
    assert "/api/v1/tasks/" in content
    assert "/ci-cd/summary" in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_adres_api_i_projekt_wchodza_przez_zmienne(platform):
    content = _content(platform)

    assert API_URL in content
    assert PROJECT_ID in content
    assert "TESTGEN_API_URL" in content
    assert "TESTGEN_PROJECT_ID" in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_kazda_konfiguracja_uwierzytelnia_sie_kluczem_api(platform):
    content = _content(platform)

    assert "Authorization: Bearer" in content
    assert API_KEY_VARIABLE in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_kazda_konfiguracja_pakuje_kod_do_archiwum(platform):
    """Upload rozpakowuje archiwa (1.6-zakańczenie) — jedno żądanie zamiast setek."""
    content = _content(platform)

    assert "zip -qr testgen-source.zip" in content
    assert "files=@testgen-source.zip" in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_kazda_konfiguracja_przerywa_build_po_przekroczeniu_progu(platform):
    content = _content(platform)

    assert "should_fail" in content
    assert "exit 1" in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_kazda_konfiguracja_ma_komentarze_po_polsku(platform):
    """AC5 — komentarze wyjaśniające kroki."""
    content = _content(platform)

    assert "TestGEN" in content
    assert any(word in content for word in ("Wymagania", "klucz API", "analizy"))


# ── treść: parametry (AC6) ───────────────────────────────────────────────────


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_prog_trafia_do_wywolania_podsumowania(platform):
    content = _content(platform, severity_threshold="high")

    assert "threshold=high" in content
    assert "threshold=critical" not in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_tryb_silnika_trafia_do_zadania_analizy(platform):
    content = _content(platform, engine_mode="hybrid")

    assert '"engine_mode": "hybrid"' in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_moduly_trafiaja_do_zadania_analizy(platform):
    content = _content(platform, modules=["code_analysis", "security_scan"])

    assert '"modules": ["code_analysis", "security_scan"]' in content


@pytest.mark.parametrize("platform", list(CicdPlatform))
def test_timeout_trafia_do_konfiguracji_i_liczby_prob(platform):
    content = _content(platform, timeout_minutes=5)

    assert "5" in content
    assert "30" in content  # 5 min * 6 prob = 30 prób odpytywania


def test_identyfikator_projektu_trafia_wszedzie():
    for platform in CicdPlatform:
        assert PROJECT_ID in _content(platform)


# ── funkcje per platforma (Task 1.1) ─────────────────────────────────────────


def test_funkcje_per_platforma_wymuszaja_swoja_platforme():
    """Nawet gdy parametry mówią co innego — nazwa funkcji jest kontraktem."""
    params = _params(platform=CicdPlatform.GITLAB_CI)

    assert "pipeline {" in generate_jenkinsfile(params)
    assert "runs-on: ubuntu-latest" in generate_github_actions(params)
    assert "vmImage: ubuntu-latest" in generate_azure_pipelines(params)
    assert "stages:\n  - test" in generate_gitlab_ci(params)


def test_generate_zwraca_komplet_metadanych():
    result = generate(_params(platform=CicdPlatform.JENKINS))

    assert result["platform"] == "jenkins"
    assert result["filename"] == "Jenkinsfile"
    assert result["language"] == "groovy"
    assert result["secret_hint"]
    assert result["content"].startswith("// Analiza TestGEN")
