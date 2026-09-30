"""Dependency / SCA scanner tests (Story 4.4).

Parsers, CVE matching via an injected fake provider, SBOM generation and finding
emission are all exercised offline (no DB, no network).
"""

import uuid

import pytest

from app.services.security_scan.dependency_scanner import (
    CVEEntry,
    Dependency,
    DependencyScanner,
)


class FakeCVEProvider:
    """Returns canned CVEs keyed by package name."""

    def __init__(self, table: dict[str, list[CVEEntry]]) -> None:
        self.table = table

    async def query(self, name, version, ecosystem):
        return list(self.table.get(name, []))


scanner = DependencyScanner()


# ----- parsers ------------------------------------------------------------


def test_parse_requirements_txt():
    deps = scanner.parse_file(
        "requirements.txt",
        "Django==3.2.0\nrequests>=2.25.1\n# comment\n-e .\nflask\n",
    )
    by = {d.name: d for d in deps}
    assert by["Django"].version == "3.2.0"
    assert by["Django"].ecosystem == "pypi"
    assert "requests" in by
    assert "flask" in by  # no version still captured


def test_parse_pyproject_toml_pep621():
    content = (
        "[project]\n"
        'name = "x"\n'
        'dependencies = ["fastapi>=0.100", "pydantic==2.5.0"]\n'
    )
    deps = scanner.parse_file("pyproject.toml", content)
    names = {d.name for d in deps}
    assert "fastapi" in names
    assert "pydantic" in names


def test_parse_pyproject_toml_poetry():
    content = (
        "[tool.poetry.dependencies]\n"
        'python = "^3.11"\n'
        'requests = "^2.31.0"\n'
    )
    deps = scanner.parse_file("pyproject.toml", content)
    names = {d.name for d in deps}
    assert "requests" in names
    assert "python" not in names  # python runtime is skipped


def test_parse_package_json():
    content = (
        '{"dependencies": {"lodash": "^4.17.20"}, '
        '"devDependencies": {"jest": "29.0.0"}}'
    )
    deps = scanner.parse_file("package.json", content)
    by = {d.name: d for d in deps}
    assert by["lodash"].ecosystem == "npm"
    assert by["lodash"].version == "4.17.20"
    assert "jest" in by  # devDependencies are captured too


def test_parse_package_lock_v3():
    content = (
        '{"lockfileVersion": 3, "packages": {'
        '"": {"name": "root"}, '
        '"node_modules/axios": {"version": "0.21.1"}}}'
    )
    deps = scanner.parse_file("package-lock.json", content)
    by = {d.name: d for d in deps}
    assert "axios" in by
    assert by["axios"].version == "0.21.1"


def test_parse_pom_xml():
    content = (
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<dependencies><dependency>"
        "<groupId>org.springframework</groupId>"
        "<artifactId>spring-core</artifactId>"
        "<version>5.3.0</version>"
        "</dependency></dependencies></project>"
    )
    deps = scanner.parse_file("pom.xml", content)
    assert len(deps) == 1
    assert deps[0].name == "org.springframework:spring-core"
    assert deps[0].version == "5.3.0"
    assert deps[0].ecosystem == "maven"


def test_parse_build_gradle():
    content = "implementation 'com.google.guava:guava:30.0-jre'\n"
    deps = scanner.parse_file("build.gradle", content)
    assert any(d.name == "com.google.guava:guava" for d in deps)


def test_parse_csproj():
    content = (
        "<Project><ItemGroup>"
        '<PackageReference Include="Newtonsoft.Json" Version="12.0.1" />'
        "</ItemGroup></Project>"
    )
    deps = scanner.parse_file("app.csproj", content)
    assert deps[0].name == "Newtonsoft.Json"
    assert deps[0].ecosystem == "nuget"


def test_parse_packages_config():
    content = '<packages><package id="jQuery" version="3.4.1" /></packages>'
    deps = scanner.parse_file("packages.config", content)
    assert deps[0].name == "jQuery"


def test_parse_composer_json():
    content = (
        '{"require": {"monolog/monolog": "2.0.0", "php": ">=7.4", '
        '"ext-json": "*"}}'
    )
    deps = scanner.parse_file("composer.json", content)
    names = {d.name for d in deps}
    assert "monolog/monolog" in names
    assert "php" not in names
    assert "ext-json" not in names


def test_unknown_file_returns_empty():
    assert scanner.parse_file("README.md", "hello") == []


def test_malformed_manifest_does_not_raise():
    assert scanner.parse_file("package.json", "{not json") == []


# ----- CVE check + findings ----------------------------------------------


@pytest.mark.asyncio
async def test_check_cve_emits_finding_above_threshold():
    cve = CVEEntry(
        cve_id="CVE-2021-1234",
        cvss_score=9.8,
        description="RCE",
        fixed_version="3.2.5",
    )
    sca = DependencyScanner(cve_provider=FakeCVEProvider({"Django": [cve]}))
    dep = Dependency(name="Django", version="3.2.0", ecosystem="pypi")
    entries = await sca._check_cve(dep)
    findings = sca._create_findings(dep, entries, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    assert len(findings) == 1
    f = findings[0]
    assert f.severity.value == "critical"
    assert f.vulnerability_type == "vulnerable_dependency"
    assert "3.2.5" in f.recommendation
    assert f.finding_metadata["cve_id"] == "CVE-2021-1234"


@pytest.mark.asyncio
async def test_low_cvss_below_threshold_no_finding():
    cve = CVEEntry(cve_id="CVE-0", cvss_score=2.0, description="minor")
    sca = DependencyScanner(cve_provider=FakeCVEProvider({"lodash": [cve]}))
    dep = Dependency(name="lodash", version="4.0.0", ecosystem="npm")
    entries = await sca._check_cve(dep)
    findings = sca._create_findings(dep, entries, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    assert findings == []


def test_cvss_to_severity_boundaries():
    assert DependencyScanner._cvss_to_severity(9.0).value == "critical"
    assert DependencyScanner._cvss_to_severity(7.5).value == "high"
    assert DependencyScanner._cvss_to_severity(4.0).value == "medium"
    assert DependencyScanner._cvss_to_severity(1.0).value == "low"


def test_merge_cve_results_dedupes_keeping_highest():
    merged = DependencyScanner._merge_cve_results(
        [
            CVEEntry(cve_id="CVE-1", cvss_score=5.0, description="a"),
            CVEEntry(cve_id="CVE-1", cvss_score=8.0, description="b", fixed_version="2.0"),
            CVEEntry(cve_id="CVE-2", cvss_score=3.0, description="c"),
        ]
    )
    by = {e.cve_id: e for e in merged}
    assert by["CVE-1"].cvss_score == 8.0
    assert by["CVE-2"].cvss_score == 3.0


# ----- SBOM ---------------------------------------------------------------


def test_generate_cyclonedx_sbom():
    deps = [Dependency(name="Django", version="3.2.0", ecosystem="pypi")]
    cve_map = {deps[0].key(): [CVEEntry(cve_id="CVE-2021-1234", cvss_score=9.8, description="x")]}
    sbom = DependencyScanner.generate_cyclonedx_sbom(deps, cve_map)
    assert sbom["bomFormat"] == "CycloneDX"
    comp = sbom["components"][0]
    assert comp["purl"] == "pkg:pypi/Django@3.2.0"
    assert comp["vulnerabilities"][0]["id"] == "CVE-2021-1234"


def test_generate_spdx_sbom():
    deps = [Dependency(name="spring-core", version="5.3.0", ecosystem="maven")]
    sbom = DependencyScanner.generate_spdx_sbom(deps, {})
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["packages"][0]["versionInfo"] == "5.3.0"
