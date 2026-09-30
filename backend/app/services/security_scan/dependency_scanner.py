"""Dependency / SCA scanner — Epic 4, Story 4.4.

Parses a project's dependency manifests across five ecosystems
(Python / npm / Maven / NuGet / Composer), checks each dependency against CVE
databases through a pluggable :class:`CVEProvider`, generates an SBOM
(CycloneDX + SPDX), and emits a :class:`SecurityFinding` per vulnerable package
(CVSS >= 4.0). Network access is abstracted behind ``CVEProvider`` so the parsers
and SBOM generation are fully offline-testable; the default provider reads the
local ``cve_database`` cache.
"""

import json
import logging
import re
import tomllib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)

logger = logging.getLogger(__name__)

# CVSS >= this threshold produces a finding (AC4).
_FINDING_CVSS_THRESHOLD = 4.0


@dataclass
class Dependency:
    name: str
    version: str | None
    ecosystem: str  # pypi / npm / maven / nuget / composer
    is_direct: bool = True
    license: str | None = None

    def key(self) -> str:
        return f"{self.ecosystem}:{self.name}@{self.version or '*'}"


@dataclass
class DependencyFile:
    path: str
    ecosystem: str
    parser_name: str


@dataclass
class CVEEntry:
    cve_id: str
    cvss_score: float
    description: str
    affected_versions: str | None = None
    fixed_version: str | None = None
    source_db: str = "osv"


class CVEProvider(Protocol):
    """Looks up known CVEs for a single dependency."""

    async def query(self, name: str, version: str | None, ecosystem: str) -> list[CVEEntry]:
        ...


class NullCVEProvider:
    """Offline default — returns no CVEs. Parsing and SBOM still work."""

    async def query(self, name: str, version: str | None, ecosystem: str) -> list[CVEEntry]:
        return []


class LocalCacheCVEProvider:
    """Serves CVEs from the local ``cve_database`` cache (no network)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def query(self, name: str, version: str | None, ecosystem: str) -> list[CVEEntry]:
        from app.models.security_finding import CVEDatabase

        result = await self.db.execute(
            select(CVEDatabase).where(
                CVEDatabase.package_name == name,
                CVEDatabase.ecosystem == ecosystem,
            )
        )
        return [
            CVEEntry(
                cve_id=row.cve_id,
                cvss_score=row.cvss_score,
                description=row.description,
                affected_versions=row.affected_versions,
                fixed_version=row.fixed_version,
                source_db=row.source_db,
            )
            for row in result.scalars().all()
        ]


# Filename -> (ecosystem, parser method). Order matters: more specific first.
_FILE_MATCHERS: tuple[tuple[str, str, str], ...] = (
    ("requirements", "pypi", "_parse_requirements_txt"),  # requirements*.txt
    ("pyproject.toml", "pypi", "_parse_pyproject_toml"),
    ("package-lock.json", "npm", "_parse_package_lock"),
    ("package.json", "npm", "_parse_package_json"),
    ("pom.xml", "maven", "_parse_pom_xml"),
    ("build.gradle", "maven", "_parse_build_gradle"),
    (".csproj", "nuget", "_parse_csproj"),
    ("packages.config", "nuget", "_parse_packages_config"),
    ("composer.json", "composer", "_parse_composer_json"),
)


class DependencyScanner:
    """SCA scanner: parse manifests, check CVEs, build SBOM, emit findings."""

    def __init__(self, db: AsyncSession | None = None, cve_provider: CVEProvider | None = None) -> None:
        self.db = db
        if cve_provider is not None:
            self.cve_provider: CVEProvider = cve_provider
        elif db is not None:
            self.cve_provider = LocalCacheCVEProvider(db)
        else:
            self.cve_provider = NullCVEProvider()

    # ----- public API ------------------------------------------------------

    def parse_file(self, filename: str, content: str) -> list[Dependency]:
        """Detect the ecosystem for ``filename`` and parse its dependencies."""
        dep_file = self._match_file(filename)
        if dep_file is None:
            return []
        parser = getattr(self, dep_file.parser_name)
        try:
            return parser(content)
        except Exception as exc:  # malformed manifest must not crash the scan
            logger.warning("Failed to parse %s: %s", filename, exc)
            return []

    async def scan_dependencies(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> tuple[list[SecurityFinding], dict]:
        """Scan a project's manifests. Returns (findings, sbom_payload)."""
        files = await self._load_dependency_files(project_id)
        dependencies: list[Dependency] = []
        for path, content in files:
            dependencies.extend(self.parse_file(path, content))

        cve_map: dict[str, list[CVEEntry]] = {}
        findings: list[SecurityFinding] = []
        for dep in dependencies:
            entries = await self._check_cve(dep)
            if entries:
                cve_map[dep.key()] = entries
            findings.extend(self._create_findings(dep, entries, project_id, tenant_id, scan_id))

        sbom = {
            "cyclonedx": self.generate_cyclonedx_sbom(dependencies, cve_map),
            "spdx": self.generate_spdx_sbom(dependencies, cve_map),
        }
        logger.info(
            "Dependency scan project=%s deps=%d vulnerable=%d findings=%d",
            project_id, len(dependencies), len(cve_map), len(findings),
        )
        return findings, sbom

    # ----- file detection --------------------------------------------------

    def _match_file(self, filename: str) -> DependencyFile | None:
        base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        for token, ecosystem, parser in _FILE_MATCHERS:
            if token.startswith("."):
                if base.endswith(token):
                    return DependencyFile(filename, ecosystem, parser)
            elif base.startswith(token) or base == token:
                return DependencyFile(filename, ecosystem, parser)
        return None

    def _detect_dependency_files(self, filenames: list[str]) -> list[DependencyFile]:
        out = []
        for name in filenames:
            match = self._match_file(name)
            if match is not None:
                out.append(match)
        return out

    # ----- parsers (pure, testable) ---------------------------------------

    @staticmethod
    def _parse_requirements_txt(content: str) -> list[Dependency]:
        deps: list[Dependency] = []
        spec = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(==|>=|<=|~=|!=|>|<)?\s*([0-9][^;\s,]*)?")
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "-", "git+", "http")):
                continue
            line = line.split("#", 1)[0].strip()
            m = spec.match(line)
            if not m:
                continue
            deps.append(Dependency(name=m.group(1), version=m.group(3), ecosystem="pypi"))
        return deps

    @staticmethod
    def _parse_pyproject_toml(content: str) -> list[Dependency]:
        data = tomllib.loads(content)
        deps: list[Dependency] = []
        spec = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[=<>!~]+\s*([0-9][^;\s,]*))?")
        # PEP 621
        for item in data.get("project", {}).get("dependencies", []) or []:
            m = spec.match(item.strip())
            if m:
                deps.append(Dependency(name=m.group(1), version=m.group(2), ecosystem="pypi"))
        # Poetry
        poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
        for name, ver in poetry.items():
            if name.lower() == "python":
                continue
            version = ver if isinstance(ver, str) else (ver.get("version") if isinstance(ver, dict) else None)
            deps.append(Dependency(name=name, version=_clean_version(version), ecosystem="pypi"))
        return deps

    @staticmethod
    def _parse_package_json(content: str) -> list[Dependency]:
        data = json.loads(content)
        deps: list[Dependency] = []
        for section, direct in (("dependencies", True), ("devDependencies", True)):
            for name, ver in (data.get(section) or {}).items():
                deps.append(
                    Dependency(name=name, version=_clean_version(ver), ecosystem="npm", is_direct=direct)
                )
        return deps

    @staticmethod
    def _parse_package_lock(content: str) -> list[Dependency]:
        data = json.loads(content)
        deps: list[Dependency] = []
        # npm lockfile v2/v3 uses "packages"; v1 uses "dependencies".
        packages = data.get("packages")
        if isinstance(packages, dict):
            for path, meta in packages.items():
                if not path or not isinstance(meta, dict):
                    continue
                name = path.split("node_modules/")[-1]
                deps.append(
                    Dependency(
                        name=name,
                        version=meta.get("version"),
                        ecosystem="npm",
                        is_direct=False,
                    )
                )
        else:
            for name, meta in (data.get("dependencies") or {}).items():
                version = meta.get("version") if isinstance(meta, dict) else None
                deps.append(Dependency(name=name, version=version, ecosystem="npm", is_direct=False))
        return deps

    @staticmethod
    def _parse_pom_xml(content: str) -> list[Dependency]:
        deps: list[Dependency] = []
        root = ET.fromstring(content)
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag[: root.tag.index("}") + 1]
        for dep in root.iter(f"{ns}dependency"):
            group = dep.findtext(f"{ns}groupId")
            artifact = dep.findtext(f"{ns}artifactId")
            version = dep.findtext(f"{ns}version")
            if artifact is None:
                continue
            name = f"{group}:{artifact}" if group else artifact
            deps.append(Dependency(name=name, version=version, ecosystem="maven"))
        return deps

    @staticmethod
    def _parse_build_gradle(content: str) -> list[Dependency]:
        deps: list[Dependency] = []
        # implementation 'group:artifact:version' / "group:artifact:version"
        pattern = re.compile(r"""['"]([\w.-]+):([\w.-]+):([\w.\-+]+)['"]""")
        for group, artifact, version in pattern.findall(content):
            deps.append(Dependency(name=f"{group}:{artifact}", version=version, ecosystem="maven"))
        return deps

    @staticmethod
    def _parse_csproj(content: str) -> list[Dependency]:
        deps: list[Dependency] = []
        root = ET.fromstring(content)
        for ref in root.iter("PackageReference"):
            name = ref.get("Include") or ref.get("Update")
            version = ref.get("Version") or ref.findtext("Version")
            if name:
                deps.append(Dependency(name=name, version=version, ecosystem="nuget"))
        return deps

    @staticmethod
    def _parse_packages_config(content: str) -> list[Dependency]:
        deps: list[Dependency] = []
        root = ET.fromstring(content)
        for pkg in root.iter("package"):
            name = pkg.get("id")
            if name:
                deps.append(Dependency(name=name, version=pkg.get("version"), ecosystem="nuget"))
        return deps

    @staticmethod
    def _parse_composer_json(content: str) -> list[Dependency]:
        data = json.loads(content)
        deps: list[Dependency] = []
        for section in ("require", "require-dev"):
            for name, ver in (data.get(section) or {}).items():
                if name.lower() == "php" or name.lower().startswith("ext-"):
                    continue
                deps.append(Dependency(name=name, version=_clean_version(ver), ecosystem="composer"))
        return deps

    # ----- CVE checking ----------------------------------------------------

    async def _check_cve(self, dep: Dependency) -> list[CVEEntry]:
        try:
            entries = await self.cve_provider.query(dep.name, dep.version, dep.ecosystem)
        except Exception as exc:
            logger.warning("CVE lookup failed for %s: %s", dep.key(), exc)
            return []
        return self._merge_cve_results(entries)

    @staticmethod
    def _merge_cve_results(entries: list[CVEEntry]) -> list[CVEEntry]:
        """Deduplicate by CVE id, keeping the highest CVSS / a known fix."""
        by_id: dict[str, CVEEntry] = {}
        for e in entries:
            existing = by_id.get(e.cve_id)
            if existing is None or e.cvss_score > existing.cvss_score:
                by_id[e.cve_id] = e
            elif existing.fixed_version is None and e.fixed_version:
                existing.fixed_version = e.fixed_version
        return list(by_id.values())

    @staticmethod
    def _cvss_to_severity(cvss: float) -> Severity:
        if cvss >= 9.0:
            return Severity.CRITICAL
        if cvss >= 7.0:
            return Severity.HIGH
        if cvss >= 4.0:
            return Severity.MEDIUM
        return Severity.LOW

    # ----- findings --------------------------------------------------------

    def _create_findings(
        self,
        dep: Dependency,
        entries: list[CVEEntry],
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for cve in entries:
            if cve.cvss_score < _FINDING_CVSS_THRESHOLD:
                continue
            if cve.fixed_version:
                recommendation = (
                    f"Zaktualizuj {dep.name} z {dep.version or '?'} do {cve.fixed_version}"
                )
            else:
                recommendation = (
                    f"Brak poprawki dla {dep.name} {dep.version or ''}; rozważ zamiennik lub mitigację."
                )
            findings.append(
                SecurityFinding(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    scan_id=scan_id,
                    scan_type=ScanType.DEPENDENCY,
                    vulnerability_type="vulnerable_dependency",
                    severity=self._cvss_to_severity(cve.cvss_score),
                    cwe_id=None,
                    owasp_category="A06:2021-Vulnerable and Outdated Components",
                    file_path=None,
                    description=(
                        f"{dep.name} {dep.version or ''} — {cve.cve_id} "
                        f"(CVSS {cve.cvss_score}): {cve.description}"
                    ).strip(),
                    confidence=0.9,
                    source=AnalysisSource.NATIVE,
                    recommendation=recommendation,
                    finding_metadata={
                        "package": dep.name,
                        "version": dep.version,
                        "ecosystem": dep.ecosystem,
                        "cve_id": cve.cve_id,
                        "cvss_score": cve.cvss_score,
                        "fixed_version": cve.fixed_version,
                        "source_db": cve.source_db,
                    },
                )
            )
        return findings

    # ----- SBOM ------------------------------------------------------------

    @staticmethod
    def generate_cyclonedx_sbom(
        dependencies: list[Dependency], cve_map: dict[str, list[CVEEntry]]
    ) -> dict:
        components = []
        for dep in dependencies:
            comp = {
                "type": "library",
                "name": dep.name,
                "version": dep.version or "",
                "purl": _to_purl(dep),
                "scope": "required" if dep.is_direct else "optional",
            }
            if dep.license:
                comp["licenses"] = [{"license": {"id": dep.license}}]
            vulns = cve_map.get(dep.key(), [])
            if vulns:
                comp["vulnerabilities"] = [
                    {"id": v.cve_id, "source": {"name": v.source_db}} for v in vulns
                ]
            components.append(comp)
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "metadata": {"timestamp": datetime.now(UTC).isoformat()},
            "components": components,
        }

    @staticmethod
    def generate_spdx_sbom(
        dependencies: list[Dependency], cve_map: dict[str, list[CVEEntry]]
    ) -> dict:
        packages = []
        for i, dep in enumerate(dependencies):
            packages.append(
                {
                    "SPDXID": f"SPDXRef-Package-{i}",
                    "name": dep.name,
                    "versionInfo": dep.version or "NOASSERTION",
                    "licenseConcluded": dep.license or "NOASSERTION",
                    "externalRefs": [
                        {
                            "referenceCategory": "PACKAGE-MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": _to_purl(dep),
                        }
                    ],
                }
            )
        return {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "testgen-dependency-sbom",
            "creationInfo": {"created": datetime.now(UTC).isoformat(), "creators": ["Tool: testgen"]},
            "packages": packages,
        }

    # ----- loading ---------------------------------------------------------

    async def _load_dependency_files(self, project_id: uuid.UUID) -> list[tuple[str, str]]:
        if self.db is None:
            return []
        import asyncio

        from app.core.config import get_settings
        from app.core.storage import download_file_bytes
        from app.models.source_file import SourceFile

        settings = get_settings()
        result = await self.db.execute(
            select(SourceFile).where(
                SourceFile.project_id == project_id,
                SourceFile.is_cleaned_up == False,  # noqa: E712
            )
        )
        files: list[tuple[str, str]] = []
        for sf in result.scalars().all():
            name = sf.original_path or sf.filename
            if self._match_file(name) is None:
                continue
            try:
                raw = await asyncio.to_thread(
                    download_file_bytes, settings.minio_bucket_name, sf.storage_key
                )
                files.append((name, raw.decode("utf-8", errors="replace")))
            except Exception as exc:
                logger.warning("Dependency scan: failed to load %s: %s", sf.storage_key, exc)
        return files


def _clean_version(spec: str | None) -> str | None:
    """Strip range operators (^ ~ >= == * spaces) to a bare version where possible."""
    if not spec:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)*(?:[.\-+][0-9A-Za-z.]+)?)", spec)
    return m.group(1) if m else None


def _to_purl(dep: Dependency) -> str:
    type_map = {"pypi": "pypi", "npm": "npm", "maven": "maven", "nuget": "nuget", "composer": "composer"}
    purl_type = type_map.get(dep.ecosystem, dep.ecosystem)
    name = dep.name
    if dep.ecosystem == "maven" and ":" in name:
        group, artifact = name.split(":", 1)
        name = f"{group}/{artifact}"
    version = f"@{dep.version}" if dep.version else ""
    return f"pkg:{purl_type}/{name}{version}"
