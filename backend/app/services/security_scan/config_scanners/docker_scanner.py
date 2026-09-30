"""Docker configuration scanner — Epic 4, Story 4.5.

Line-based analysis of ``Dockerfile`` plus a light YAML pass over
``docker-compose.yml``. Detects: running as root (or no USER), exposing internal
ports, hardcoded secrets, missing HEALTHCHECK, ``:latest`` base images and
``sudo`` usage.
"""

import re

from app.services.security_scan.config_scanners.base import ConfigFinding

# Internal services that should not be exposed from a container image.
_SENSITIVE_PORTS = {"22", "23", "3306", "5432", "6379", "27017", "9200", "5984"}

_SECRET_KEY_RE = re.compile(
    r"\b([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|APIKEY|API_KEY|ACCESS_KEY|PRIVATE_KEY)[A-Z0-9_]*)\b",
    re.IGNORECASE,
)
_FROM_RE = re.compile(r"^FROM\s+(\S+)", re.IGNORECASE)
_EXPOSE_RE = re.compile(r"^EXPOSE\s+(.+)", re.IGNORECASE)
_USER_RE = re.compile(r"^USER\s+(\S+)", re.IGNORECASE)
_ENV_RE = re.compile(r"^(?:ENV|ARG)\s+(.+)", re.IGNORECASE)


class DockerScanner:
    config_type = "docker"

    def scan(self, content: str, filename: str) -> list[ConfigFinding]:
        base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        if base.startswith("docker-compose") or base.endswith(("compose.yml", "compose.yaml")):
            return self._scan_compose(content, filename)
        return self._scan_dockerfile(content, filename)

    # ----- Dockerfile ------------------------------------------------------

    def _scan_dockerfile(self, content: str, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        has_user_nonroot = False
        has_healthcheck = False
        last_user_root_line: int | None = None

        for idx, raw in enumerate(content.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            m = _FROM_RE.match(line)
            if m:
                image = m.group(1)
                if ":" not in image.split("/")[-1] or image.endswith(":latest"):
                    findings.append(
                        ConfigFinding(
                            rule_id="LATEST_TAG",
                            config_type=self.config_type,
                            severity="medium",
                            description=f"Obraz bazowy '{image}' bez przypiętej wersji (:latest lub brak tagu).",
                            recommendation="Przypnij konkretną wersję obrazu bazowego.",
                            fix_example="FROM python:3.13-slim",
                            file_path=filename,
                            line=idx,
                            vulnerability_type="unpinned_base_image",
                            cwe_id="CWE-1104",
                        )
                    )

            m = _USER_RE.match(line)
            if m:
                if m.group(1).lower() in ("root", "0"):
                    last_user_root_line = idx
                else:
                    has_user_nonroot = True

            if line.upper().startswith("HEALTHCHECK"):
                has_healthcheck = True

            m = _EXPOSE_RE.match(line)
            if m:
                for port in re.findall(r"\d+", m.group(1)):
                    if port in _SENSITIVE_PORTS:
                        findings.append(
                            ConfigFinding(
                                rule_id="EXPOSED_PORT",
                                config_type=self.config_type,
                                severity="medium",
                                description=f"Eksponowany wrażliwy port wewnętrzny {port}.",
                                recommendation="Nie eksponuj portów usług wewnętrznych z obrazu.",
                                fix_example="# usuń EXPOSE dla portów baz danych / SSH",
                                file_path=filename,
                                line=idx,
                                vulnerability_type="exposed_port",
                                cwe_id="CWE-668",
                            )
                        )

            if _ENV_RE.match(line) and _SECRET_KEY_RE.search(line) and "=" in line:
                value = line.split("=", 1)[1].strip()
                if value and not value.startswith("$"):
                    findings.append(
                        ConfigFinding(
                            rule_id="HARDCODED_SECRET",
                            config_type=self.config_type,
                            severity="critical",
                            description="Zaszyty sekret w instrukcji ENV/ARG.",
                            recommendation="Przekazuj sekrety przez runtime secrets / zmienne środowiskowe, nie zapisuj w obrazie.",
                            fix_example="# użyj docker secrets lub --build-arg bez wartości domyślnej",
                            file_path=filename,
                            line=idx,
                            vulnerability_type="hardcoded_secret",
                            cwe_id="CWE-798",
                        )
                    )

            if re.search(r"\bsudo\b", line) and line.upper().startswith("RUN"):
                findings.append(
                    ConfigFinding(
                        rule_id="SUDO_IN_DOCKER",
                        config_type=self.config_type,
                        severity="high",
                        description="Użycie 'sudo' w instrukcji RUN.",
                        recommendation="Uruchamiaj polecenia jako odpowiedni użytkownik bez sudo.",
                        fix_example="RUN apt-get update && apt-get install -y <pakiet>",
                        file_path=filename,
                        line=idx,
                        vulnerability_type="privilege_escalation",
                        cwe_id="CWE-250",
                    )
                )

        if not has_user_nonroot:
            findings.append(
                ConfigFinding(
                    rule_id="ROOT_USER",
                    config_type=self.config_type,
                    severity="high",
                    description=(
                        "Kontener działa jako root (jawnie USER root)."
                        if last_user_root_line
                        else "Brak instrukcji USER — kontener domyślnie działa jako root."
                    ),
                    recommendation="Dodaj nieuprzywilejowanego użytkownika i przełącz się na niego.",
                    fix_example="RUN useradd -m app\nUSER app",
                    file_path=filename,
                    line=last_user_root_line,
                    vulnerability_type="run_as_root",
                    cwe_id="CWE-250",
                )
            )

        if not has_healthcheck:
            findings.append(
                ConfigFinding(
                    rule_id="NO_HEALTHCHECK",
                    config_type=self.config_type,
                    severity="low",
                    description="Brak instrukcji HEALTHCHECK w obrazie.",
                    recommendation="Dodaj HEALTHCHECK, aby orchestrator wykrywał niezdrowe kontenery.",
                    fix_example="HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1",
                    file_path=filename,
                    line=None,
                    vulnerability_type="missing_healthcheck",
                    cwe_id="CWE-754",
                )
            )

        return findings

    # ----- docker-compose --------------------------------------------------

    def _scan_compose(self, content: str, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        for idx, raw in enumerate(content.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("privileged:") and "true" in line.lower():
                findings.append(
                    ConfigFinding(
                        rule_id="PRIVILEGED_CONTAINER",
                        config_type=self.config_type,
                        severity="critical",
                        description="Serwis compose uruchamiany w trybie privileged.",
                        recommendation="Usuń 'privileged: true'; nadawaj tylko wymagane capabilities.",
                        fix_example="cap_add:\n  - NET_ADMIN",
                        file_path=filename,
                        line=idx,
                        vulnerability_type="privileged_container",
                        cwe_id="CWE-250",
                    )
                )
            if _SECRET_KEY_RE.search(line) and ("=" in line or ":" in line):
                value = re.split(r"[:=]", line, maxsplit=1)[1].strip().strip('"').strip("'")
                if value and not value.startswith(("$", "{")):
                    findings.append(
                        ConfigFinding(
                            rule_id="HARDCODED_SECRET",
                            config_type=self.config_type,
                            severity="critical",
                            description="Zaszyty sekret w docker-compose.",
                            recommendation="Użyj plików .env lub docker secrets zamiast wartości jawnych.",
                            fix_example="environment:\n  - DB_PASSWORD=${DB_PASSWORD}",
                            file_path=filename,
                            line=idx,
                            vulnerability_type="hardcoded_secret",
                            cwe_id="CWE-798",
                        )
                    )
        return findings
