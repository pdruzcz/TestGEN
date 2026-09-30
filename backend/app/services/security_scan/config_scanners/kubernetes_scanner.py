"""Kubernetes manifest scanner — Epic 4, Story 4.5.

Parses one or more YAML documents and inspects workload specs for: missing
resource limits, privileged containers, host network, default namespace and
containers allowed to run as root.
"""

import logging

import yaml

from app.services.security_scan.config_scanners.base import ConfigFinding

logger = logging.getLogger(__name__)

_WORKLOAD_KINDS = {
    "Pod",
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "ReplicaSet",
    "Job",
    "CronJob",
}


class KubernetesScanner:
    config_type = "kubernetes"

    def scan(self, content: str, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as exc:
            logger.warning("K8s scan: invalid YAML in %s: %s", filename, exc)
            return []

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind")
            if kind not in _WORKLOAD_KINDS:
                continue
            findings.extend(self._scan_workload(doc, filename))
        return findings

    def _scan_workload(self, doc: dict, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        metadata = doc.get("metadata") or {}
        namespace = metadata.get("namespace")
        if not namespace or namespace == "default":
            findings.append(
                ConfigFinding(
                    rule_id="DEFAULT_NAMESPACE",
                    config_type=self.config_type,
                    severity="low",
                    description="Workload wdrażany w namespace 'default'.",
                    recommendation="Wdrażaj do dedykowanego namespace z politykami dostępu.",
                    fix_example="metadata:\n  namespace: production",
                    file_path=filename,
                    vulnerability_type="default_namespace",
                    cwe_id="CWE-1188",
                )
            )

        pod_spec = self._pod_spec(doc)
        if pod_spec is None:
            return findings

        if pod_spec.get("hostNetwork") is True:
            findings.append(
                ConfigFinding(
                    rule_id="HOST_NETWORK",
                    config_type=self.config_type,
                    severity="high",
                    description="Pod używa hostNetwork: true.",
                    recommendation="Wyłącz hostNetwork; korzystaj z sieci klastra i Services.",
                    fix_example="spec:\n  hostNetwork: false",
                    file_path=filename,
                    vulnerability_type="host_network",
                    cwe_id="CWE-668",
                )
            )

        pod_security = pod_spec.get("securityContext") or {}
        containers = list(pod_spec.get("containers") or [])
        containers += list(pod_spec.get("initContainers") or [])

        for container in containers:
            if not isinstance(container, dict):
                continue
            name = container.get("name", "<container>")
            sec = container.get("securityContext") or {}

            if sec.get("privileged") is True:
                findings.append(
                    ConfigFinding(
                        rule_id="PRIVILEGED_CONTAINER",
                        config_type=self.config_type,
                        severity="critical",
                        description=f"Kontener '{name}' działa w trybie privileged.",
                        recommendation="Usuń privileged; nadawaj minimalne capabilities.",
                        fix_example="securityContext:\n  privileged: false",
                        file_path=filename,
                        vulnerability_type="privileged_container",
                        cwe_id="CWE-250",
                        extra={"container": name},
                    )
                )

            run_as_non_root = sec.get("runAsNonRoot")
            if run_as_non_root is None:
                run_as_non_root = pod_security.get("runAsNonRoot")
            if run_as_non_root is not True:
                findings.append(
                    ConfigFinding(
                        rule_id="RUN_AS_ROOT",
                        config_type=self.config_type,
                        severity="high",
                        description=f"Kontener '{name}' może działać jako root (brak runAsNonRoot).",
                        recommendation="Ustaw securityContext.runAsNonRoot: true.",
                        fix_example="securityContext:\n  runAsNonRoot: true",
                        file_path=filename,
                        vulnerability_type="run_as_root",
                        cwe_id="CWE-250",
                        extra={"container": name},
                    )
                )

            resources = container.get("resources") or {}
            limits = resources.get("limits")
            requests = resources.get("requests")
            if not limits or not requests:
                findings.append(
                    ConfigFinding(
                        rule_id="NO_RESOURCE_LIMITS",
                        config_type=self.config_type,
                        severity="medium",
                        description=f"Kontener '{name}' bez resources.limits/requests.",
                        recommendation="Zdefiniuj limity i żądania CPU/pamięci.",
                        fix_example="resources:\n  limits:\n    cpu: \"500m\"\n    memory: \"256Mi\"",
                        file_path=filename,
                        vulnerability_type="missing_resource_limits",
                        cwe_id="CWE-770",
                        extra={"container": name},
                    )
                )

        return findings

    @staticmethod
    def _pod_spec(doc: dict) -> dict | None:
        kind = doc.get("kind")
        spec = doc.get("spec") or {}
        if kind == "Pod":
            return spec
        if kind == "CronJob":
            return (
                ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}
            ).get("spec")
        template = spec.get("template") or {}
        return template.get("spec")
