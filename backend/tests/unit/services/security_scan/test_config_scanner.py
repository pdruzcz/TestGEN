"""Config scanner orchestrator tests (Story 4.5) — routing + finding conversion."""

import uuid

from app.models.security_finding import ScanType
from app.services.security_scan.config_scanner import ConfigScanner

scanner = ConfigScanner()


def test_classify_routes_by_filename():
    assert scanner._classify("Dockerfile") == "docker"
    assert scanner._classify("api.dockerfile") == "docker"
    assert scanner._classify("docker-compose.yml") == "docker"
    assert scanner._classify("main.tf") == "terraform"
    assert scanner._classify("deployment.yaml") == "kubernetes"
    assert scanner._classify("README.md") is None


def test_scan_content_dockerfile():
    findings = scanner.scan_content("FROM ubuntu:latest\n", "Dockerfile")
    assert any(f.rule_id == "LATEST_TAG" for f in findings)


def test_scan_content_unknown_returns_empty():
    assert scanner.scan_content("hello", "notes.txt") == []


def test_detect_config_files():
    detected = scanner._detect_config_files(
        ["Dockerfile", "k8s/deployment.yaml", "infra/main.tf", "src/app.py"]
    )
    types = {c.config_type for c in detected}
    assert types == {"docker", "kubernetes", "terraform"}


def test_to_finding_maps_to_security_finding():
    raw = scanner.scan_content("FROM ubuntu:latest\n", "Dockerfile")[0]
    pid, tid, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    finding = scanner._to_finding(raw, pid, tid, sid)
    assert finding.scan_type == ScanType.CONFIG
    assert finding.owasp_category == "A05:2021-Security Misconfiguration"
    assert finding.finding_metadata["config_type"] == "docker"
    assert finding.finding_metadata["rule_id"] == raw.rule_id


def test_merge_findings_dedupes_and_marks_hybrid():
    native = scanner.scan_content("FROM ubuntu:latest\nUSER app\n", "Dockerfile")
    merged = scanner._merge_findings(native, list(native))
    assert len(merged) == len(native)
    assert all(f.source == "hybrid" for f in merged)
