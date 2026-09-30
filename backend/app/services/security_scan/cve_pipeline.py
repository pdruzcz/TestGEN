"""CVE auto-update pipeline — Epic 4, Story 4.12.

Periodically refreshes the local ``cve_database`` cache from three public sources
(NVD, OSV.dev, GitHub Advisory Database), deduplicates by CVE id, upserts the
result, then finds affected projects, triggers a dependency re-scan and notifies
owners. Optionally (LLM path) auto-generates a SAST rule for a new vulnerability
type and validates it on golden data.

Network access is abstracted behind an injectable ``httpx.AsyncClient`` and the
JSON parsers are pure/static, so merging, deduplication, persistence-shaping,
affected-project matching and rule parsing are all fully offline-testable.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import CVEDatabase, Severity
from app.services.security_scan.rules.base import PY, RulePattern, VulnerabilityRule

logger = logging.getLogger(__name__)

# How far back to look on the very first run (no prior successful update).
_DEFAULT_LOOKBACK = timedelta(days=30)
# OSV ecosystems we mirror into the cache.
_OSV_ECOSYSTEMS = ("PyPI", "npm", "Maven", "NuGet", "Packagist")
# Acceptable false-positive rate for an LLM-generated rule (AC3).
_MAX_FPR = 0.05

# External-source ecosystem label -> our canonical label.
_ECOSYSTEM_MAP = {
    "pypi": "pypi",
    "pip": "pypi",
    "npm": "npm",
    "maven": "maven",
    "nuget": "nuget",
    "packagist": "composer",
    "composer": "composer",
}


def _normalize_ecosystem(raw: str | None) -> str:
    return _ECOSYSTEM_MAP.get((raw or "").strip().lower(), (raw or "generic").strip().lower())


def _cvss_to_severity(cvss: float) -> Severity:
    if cvss >= 9.0:
        return Severity.CRITICAL
    if cvss >= 7.0:
        return Severity.HIGH
    if cvss >= 4.0:
        return Severity.MEDIUM
    if cvss > 0.0:
        return Severity.LOW
    return Severity.INFO


@dataclass
class CVERecord:
    """A normalized CVE entry destined for the ``cve_database`` cache."""

    cve_id: str
    package_name: str
    ecosystem: str
    cvss_score: float
    description: str
    severity: Severity = Severity.INFO
    affected_versions: str | None = None
    fixed_version: str | None = None
    published_date: datetime | None = None
    source_db: str = "osv"

    def key(self) -> tuple[str, str]:
        return (self.cve_id, self.package_name)


@dataclass
class SourceStatus:
    source: str
    ok: bool
    fetched: int = 0
    error: str | None = None


@dataclass
class AffectedProject:
    project_id: uuid.UUID
    project_name: str
    owner_id: uuid.UUID | None
    affected_packages: list[str] = field(default_factory=list)
    new_cves: list[str] = field(default_factory=list)


@dataclass
class RuleValidation:
    rule_id: str
    fpr: float
    passed: bool
    sample_size: int = 0


@dataclass
class CVEUpdateResult:
    total_new: int = 0
    total_updated: int = 0
    affected_projects: int = 0
    sources_status: dict[str, SourceStatus] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class CVEPipeline:
    """Fetch → merge → upsert → re-scan → notify pipeline for CVE data."""

    NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    OSV_URL = "https://api.osv.dev/v1/query"
    GITHUB_URL = "https://api.github.com/advisories"

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        llm_gateway=None,
        registry=None,
        nvd_api_key: str | None = None,
        github_token: str | None = None,
    ) -> None:
        self._client = http_client
        self._llm = llm_gateway
        self._registry = registry
        self._nvd_api_key = nvd_api_key
        self._github_token = github_token

    # ----- orchestration ---------------------------------------------------

    async def update_cve_database(self, db: AsyncSession) -> CVEUpdateResult:
        """Run the full update cycle and return aggregated statistics (AC1, AC2)."""
        result = CVEUpdateResult()
        since = await self._get_last_update_date(db)
        logger.info("CVE pipeline starting — fetching updates since %s", since.isoformat())

        by_source: dict[str, list[CVERecord]] = {}
        for source, fetch in (
            ("nvd", self._fetch_nvd_updates),
            ("osv", self._fetch_osv_updates),
            ("github", self._fetch_github_advisories),
        ):
            try:
                records = await fetch(since)
                by_source[source] = records
                result.sources_status[source] = SourceStatus(source, ok=True, fetched=len(records))
            except Exception as exc:  # one bad source must not abort the others
                by_source[source] = []
                result.sources_status[source] = SourceStatus(source, ok=False, error=str(exc)[:300])
                result.errors.append(f"{source}: {exc}")
                logger.warning("CVE source %s failed: %s", source, exc)

        merged = self._merge_and_deduplicate(by_source)
        new, updated = await self._save_to_database(merged, db)
        result.total_new = new
        result.total_updated = updated

        affected = await self._find_affected_projects(merged, db)
        result.affected_projects = len(affected)
        if affected:
            self._trigger_dependency_rescan([a.project_id for a in affected])
            await self._send_notifications(affected, db)

        logger.info(
            "CVE pipeline done — new=%d updated=%d affected_projects=%d",
            new, updated, len(affected),
        )
        return result

    async def _get_last_update_date(self, db: AsyncSession) -> datetime:
        from app.models.security_finding import CVEUpdateLog

        result = await db.execute(
            select(CVEUpdateLog.completed_at)
            .where(CVEUpdateLog.status == "completed")
            .order_by(CVEUpdateLog.completed_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        return last or (datetime.now(UTC) - _DEFAULT_LOOKBACK)

    # ----- fetching (network) ---------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        return self._client

    async def _fetch_nvd_updates(self, since: datetime) -> list[CVERecord]:
        client = await self._get_client()
        headers = {"apiKey": self._nvd_api_key} if self._nvd_api_key else {}
        params = {
            "pubStartDate": since.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": 2000,
            "startIndex": 0,
        }
        resp = await client.get(self.NVD_URL, params=params, headers=headers)
        resp.raise_for_status()
        return self._parse_nvd(resp.json())

    async def _fetch_osv_updates(self, since: datetime) -> list[CVERecord]:
        client = await self._get_client()
        records: list[CVERecord] = []
        for ecosystem in _OSV_ECOSYSTEMS:
            resp = await client.post(self.OSV_URL, json={"ecosystem": ecosystem})
            resp.raise_for_status()
            records.extend(self._parse_osv(resp.json(), ecosystem))
        return records

    async def _fetch_github_advisories(self, since: datetime) -> list[CVERecord]:
        client = await self._get_client()
        headers = {"Accept": "application/vnd.github+json"}
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"
        params = {"per_page": 100, "published": f">{since.strftime('%Y-%m-%d')}"}
        resp = await client.get(self.GITHUB_URL, params=params, headers=headers)
        resp.raise_for_status()
        return self._parse_github(resp.json())

    # ----- parsing (pure / static) ----------------------------------------

    @staticmethod
    def _parse_nvd(payload: dict) -> list[CVERecord]:
        records: list[CVERecord] = []
        for item in payload.get("vulnerabilities", []) or []:
            cve = item.get("cve", {})
            cve_id = cve.get("id")
            if not cve_id:
                continue
            description = next(
                (d.get("value", "") for d in cve.get("descriptions", []) if d.get("lang") == "en"),
                "",
            )
            cvss = CVEPipeline._nvd_base_score(cve.get("metrics", {}))
            published = _parse_dt(cve.get("published"))
            packages = CVEPipeline._nvd_packages(cve.get("configurations", []))
            if not packages:
                packages = [("", "generic")]
            for name, ecosystem in packages:
                records.append(
                    CVERecord(
                        cve_id=cve_id,
                        package_name=name,
                        ecosystem=_normalize_ecosystem(ecosystem),
                        cvss_score=cvss,
                        description=description,
                        severity=_cvss_to_severity(cvss),
                        published_date=published,
                        source_db="nvd",
                    )
                )
        return records

    @staticmethod
    def _nvd_base_score(metrics: dict) -> float:
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            for metric in metrics.get(key, []) or []:
                score = metric.get("cvssData", {}).get("baseScore")
                if isinstance(score, (int, float)):
                    return float(score)
        return 0.0

    @staticmethod
    def _nvd_packages(configurations: list) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for config in configurations or []:
            for node in config.get("nodes", []) or []:
                for match in node.get("cpeMatch", []) or []:
                    criteria = match.get("criteria", "")
                    # cpe:2.3:a:vendor:product:version:...
                    parts = criteria.split(":")
                    if len(parts) > 4 and parts[4] not in ("*", "-", ""):
                        out.append((parts[4], "generic"))
        return out

    @staticmethod
    def _parse_osv(payload: dict, ecosystem: str) -> list[CVERecord]:
        records: list[CVERecord] = []
        for vuln in payload.get("vulns", []) or []:
            osv_id = vuln.get("id", "")
            cve_id = next((a for a in vuln.get("aliases", []) if a.startswith("CVE-")), osv_id)
            description = vuln.get("summary") or vuln.get("details", "") or ""
            cvss = CVEPipeline._osv_score(vuln.get("severity", []))
            severity_label = vuln.get("database_specific", {}).get("severity")
            severity = _label_to_severity(severity_label) if severity_label else _cvss_to_severity(cvss)
            published = _parse_dt(vuln.get("published"))
            for affected in vuln.get("affected", []) or []:
                pkg = affected.get("package", {})
                name = pkg.get("name")
                if not name:
                    continue
                versions = affected.get("versions") or []
                fixed = CVEPipeline._osv_fixed_version(affected.get("ranges", []))
                records.append(
                    CVERecord(
                        cve_id=cve_id,
                        package_name=name,
                        ecosystem=_normalize_ecosystem(pkg.get("ecosystem") or ecosystem),
                        cvss_score=cvss,
                        description=description,
                        severity=severity,
                        affected_versions=", ".join(versions[:20]) if versions else None,
                        fixed_version=fixed,
                        published_date=published,
                        source_db="osv",
                    )
                )
        return records

    @staticmethod
    def _osv_score(severity: list) -> float:
        for entry in severity or []:
            score = entry.get("score", "")
            m = re.search(r"baseScore[:=]?\s*([0-9]+\.?[0-9]*)", str(score))
            if m:
                return float(m.group(1))
            if isinstance(score, (int, float)):
                return float(score)
        return 0.0

    @staticmethod
    def _osv_fixed_version(ranges: list) -> str | None:
        for rng in ranges or []:
            for event in rng.get("events", []) or []:
                if "fixed" in event:
                    return event["fixed"]
        return None

    @staticmethod
    def _parse_github(payload) -> list[CVERecord]:
        records: list[CVERecord] = []
        items = payload if isinstance(payload, list) else payload.get("advisories", [])
        for adv in items or []:
            cve_id = adv.get("cve_id") or adv.get("ghsa_id", "")
            description = adv.get("summary") or adv.get("description", "") or ""
            cvss = float(adv.get("cvss", {}).get("score") or 0.0)
            severity = _label_to_severity(adv.get("severity")) if adv.get("severity") else _cvss_to_severity(cvss)
            published = _parse_dt(adv.get("published_at"))
            for vuln in adv.get("vulnerabilities", []) or []:
                pkg = vuln.get("package", {})
                name = pkg.get("name")
                if not name:
                    continue
                patched = vuln.get("first_patched_version")
                fixed = patched.get("identifier") if isinstance(patched, dict) else patched
                records.append(
                    CVERecord(
                        cve_id=cve_id,
                        package_name=name,
                        ecosystem=_normalize_ecosystem(pkg.get("ecosystem")),
                        cvss_score=cvss,
                        description=description,
                        severity=severity,
                        affected_versions=vuln.get("vulnerable_version_range"),
                        fixed_version=fixed,
                        published_date=published,
                        source_db="github",
                    )
                )
        return records

    # ----- merge -----------------------------------------------------------

    @staticmethod
    def _merge_and_deduplicate(by_source: dict[str, list[CVERecord]]) -> list[CVERecord]:
        """Deduplicate by (cve_id, package_name), keeping the richest record.

        Higher CVSS wins; a known fix is preferred over none. Source order (NVD,
        OSV, GitHub) breaks exact ties so output is deterministic.
        """
        merged: dict[tuple[str, str], CVERecord] = {}
        for source in ("nvd", "osv", "github"):
            for rec in by_source.get(source, []) or []:
                if not rec.cve_id or not rec.cve_id.startswith(("CVE-", "GHSA-")):
                    continue
                existing = merged.get(rec.key())
                if existing is None:
                    merged[rec.key()] = rec
                    continue
                if rec.cvss_score > existing.cvss_score:
                    merged[rec.key()] = rec
                elif existing.fixed_version is None and rec.fixed_version:
                    existing.fixed_version = rec.fixed_version
        return list(merged.values())

    # ----- persistence -----------------------------------------------------

    async def _save_to_database(self, records: list[CVERecord], db: AsyncSession) -> tuple[int, int]:
        """Upsert records into ``cve_database``. Returns (new, updated)."""
        new = 0
        updated = 0
        for rec in records:
            if not rec.package_name:
                continue
            existing = await db.execute(
                select(CVEDatabase).where(
                    CVEDatabase.cve_id == rec.cve_id,
                    CVEDatabase.package_name == rec.package_name,
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                db.add(
                    CVEDatabase(
                        cve_id=rec.cve_id,
                        package_name=rec.package_name,
                        ecosystem=rec.ecosystem,
                        cvss_score=rec.cvss_score,
                        severity=rec.severity,
                        description=rec.description,
                        affected_versions=rec.affected_versions,
                        fixed_version=rec.fixed_version,
                        published_date=rec.published_date,
                        source_db=rec.source_db,
                    )
                )
                new += 1
            else:
                row.cvss_score = rec.cvss_score
                row.severity = rec.severity
                row.description = rec.description or row.description
                row.affected_versions = rec.affected_versions or row.affected_versions
                row.fixed_version = rec.fixed_version or row.fixed_version
                row.source_db = rec.source_db
                updated += 1
        await db.flush()
        return new, updated

    # ----- affected projects / re-scan / notify ---------------------------

    @staticmethod
    def _match_affected(findings: list, records: list[CVERecord]) -> list[AffectedProject]:
        """Pure matcher: group dependency findings by project, attach new CVEs.

        ``findings`` are SecurityFinding-like objects whose ``finding_metadata``
        carries ``package``/``ecosystem`` (from the dependency scanner).
        """
        by_pkg: dict[tuple[str, str], list[str]] = {}
        for rec in records:
            by_pkg.setdefault((rec.package_name, rec.ecosystem), []).append(rec.cve_id)

        projects: dict[uuid.UUID, AffectedProject] = {}
        for finding in findings:
            meta = getattr(finding, "finding_metadata", None) or {}
            pkg = meta.get("package")
            ecosystem = _normalize_ecosystem(meta.get("ecosystem"))
            cves = by_pkg.get((pkg, ecosystem))
            if not cves:
                continue
            pid = finding.project_id
            ap = projects.get(pid)
            if ap is None:
                ap = AffectedProject(
                    project_id=pid,
                    project_name=getattr(finding, "project_name", "") or "",
                    owner_id=getattr(finding, "owner_id", None),
                )
                projects[pid] = ap
            if pkg not in ap.affected_packages:
                ap.affected_packages.append(pkg)
            for cve in cves:
                if cve not in ap.new_cves:
                    ap.new_cves.append(cve)
        return list(projects.values())

    async def _find_affected_projects(self, records: list[CVERecord], db: AsyncSession) -> list[AffectedProject]:
        if not records:
            return []
        from app.models.security_finding import ScanType, SecurityFinding

        result = await db.execute(
            select(SecurityFinding).where(SecurityFinding.scan_type == ScanType.DEPENDENCY)
        )
        findings = list(result.scalars().all())
        return self._match_affected(findings, records)

    def _trigger_dependency_rescan(self, project_ids: list[uuid.UUID]) -> None:
        """Queue a best-effort dependency re-scan per affected project (AC2)."""
        try:
            from app.workers.cve_tasks import rescan_affected_projects

            rescan_affected_projects.delay([str(pid) for pid in project_ids])
        except Exception as exc:  # broker may be unavailable in some contexts
            logger.warning("Could not enqueue re-scan for %d projects: %s", len(project_ids), exc)

    async def _send_notifications(self, affected: list[AffectedProject], db: AsyncSession) -> None:
        """Notify project owners about new vulnerabilities (AC2).

        In-app notifications have no model yet; we log a structured notification
        per owner so the signal is preserved and an email hook can be added later.
        """
        for ap in affected:
            logger.info(
                "CVE notify owner=%s project=%s packages=%s new_cves=%s",
                ap.owner_id, ap.project_id, ap.affected_packages, ap.new_cves,
            )

    # ----- LLM auto-rules (AC3) -------------------------------------------

    async def _generate_sast_rules(self, records: list[CVERecord]) -> list[VulnerabilityRule]:
        if self._llm is None:
            return []
        from app.services.analysis.llm_gateway import LLMMessage

        rules: list[VulnerabilityRule] = []
        for rec in records:
            prompt = (
                f"Na podstawie opisu CVE {rec.cve_id}: {rec.description}\n"
                "Wygeneruj jeden wzorzec wyrażenia regularnego (Python re) wykrywający tę "
                "podatność w kodzie źródłowym. Odpowiedz wyłącznie w formacie:\n"
                "REGEX: <wzorzec>\nTYPE: <typ_podatnosci>\nCWE: <CWE-xxx>"
            )
            try:
                response = await self._llm.complete(
                    provider="anthropic",
                    messages=[LLMMessage(role="user", content=prompt)],
                    max_tokens=300,
                    temperature=0.0,
                    module="security",
                    task_type="cve_rule_generation",
                )
                rule = self._parse_rule_response(response.content, rec)
            except Exception as exc:
                logger.warning("LLM rule generation failed for %s: %s", rec.cve_id, exc)
                rule = None
            if rule is not None:
                rules.append(rule)
        return rules

    @staticmethod
    def _parse_rule_response(text: str, rec: CVERecord) -> VulnerabilityRule | None:
        """Parse the constrained LLM response into a VulnerabilityRule."""
        regex_match = re.search(r"REGEX:\s*(.+)", text or "")
        if not regex_match:
            return None
        pattern_src = regex_match.group(1).strip()
        try:
            compiled = re.compile(pattern_src, re.IGNORECASE)
        except re.error:
            return None
        vuln_type = (re.search(r"TYPE:\s*(.+)", text or "") or [None, "cve_pattern"])[1]
        cwe = (re.search(r"CWE:\s*(CWE-\d+)", text or "") or [None, "CWE-0"])[1]
        return VulnerabilityRule(
            id=f"cve-{rec.cve_id.lower()}",
            name=f"Auto rule {rec.cve_id}",
            vulnerability_type=str(vuln_type).strip(),
            cwe_id=str(cwe).strip(),
            owasp_category="A06:2021-Vulnerable and Outdated Components",
            severity=rec.severity.value,
            description=rec.description[:300],
            patterns=(RulePattern(regex=compiled, languages=PY, confidence_weight=0.3),),
            recommendation=f"Sprawdź użycie wzorca związanego z {rec.cve_id}.",
            base_confidence=0.5,
        )

    @staticmethod
    def _validate_rule_on_golden_data(rule: VulnerabilityRule, safe_samples: list[str]) -> RuleValidation:
        """Compute false-positive rate against known-safe snippets (AC3, FPR<5%)."""
        if not safe_samples:
            return RuleValidation(rule_id=rule.id, fpr=0.0, passed=True, sample_size=0)
        false_positives = 0
        for sample in safe_samples:
            if any(p.regex.search(sample) for p in rule.patterns):
                false_positives += 1
        fpr = false_positives / len(safe_samples)
        return RuleValidation(
            rule_id=rule.id,
            fpr=fpr,
            passed=fpr < _MAX_FPR,
            sample_size=len(safe_samples),
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _label_to_severity(label: str | None) -> Severity:
    mapping = {
        "critical": Severity.CRITICAL,
        "high": Severity.HIGH,
        "moderate": Severity.MEDIUM,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
    }
    return mapping.get((label or "").strip().lower(), Severity.INFO)
