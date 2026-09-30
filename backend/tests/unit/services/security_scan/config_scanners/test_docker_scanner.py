"""Docker scanner tests (Story 4.5)."""

from app.services.security_scan.config_scanners.docker_scanner import DockerScanner

scanner = DockerScanner()


def _rules(content, filename="Dockerfile"):
    return {f.rule_id for f in scanner.scan(content, filename)}


def test_no_user_flags_root():
    rules = _rules("FROM python:3.13-slim\nRUN echo hi\n")
    assert "ROOT_USER" in rules


def test_explicit_nonroot_user_clears_root():
    rules = _rules("FROM python:3.13-slim\nUSER app\nHEALTHCHECK CMD true\n")
    assert "ROOT_USER" not in rules


def test_latest_tag_detected():
    assert "LATEST_TAG" in _rules("FROM ubuntu:latest\nUSER app\n")


def test_untagged_image_detected():
    assert "LATEST_TAG" in _rules("FROM ubuntu\nUSER app\n")


def test_exposed_sensitive_port():
    assert "EXPOSED_PORT" in _rules("FROM x:1\nUSER app\nEXPOSE 5432\n")


def test_hardcoded_secret_env():
    rules = _rules("FROM x:1\nUSER app\nENV DB_PASSWORD=hunter2\n")
    assert "HARDCODED_SECRET" in rules


def test_env_secret_from_arg_reference_not_flagged():
    rules = _rules("FROM x:1\nUSER app\nENV API_TOKEN=$BUILD_TOKEN\n")
    assert "HARDCODED_SECRET" not in rules


def test_sudo_in_run():
    assert "SUDO_IN_DOCKER" in _rules("FROM x:1\nUSER app\nRUN sudo apt-get update\n")


def test_missing_healthcheck():
    assert "NO_HEALTHCHECK" in _rules("FROM x:1\nUSER app\n")


def test_compose_privileged_and_secret():
    compose = (
        "services:\n"
        "  db:\n"
        "    image: postgres:16\n"
        "    privileged: true\n"
        "    environment:\n"
        "      POSTGRES_PASSWORD: secretvalue\n"
    )
    rules = _rules(compose, "docker-compose.yml")
    assert "PRIVILEGED_CONTAINER" in rules
    assert "HARDCODED_SECRET" in rules


def test_findings_carry_recommendation_and_fix():
    findings = scanner.scan("FROM ubuntu:latest\n", "Dockerfile")
    for f in findings:
        assert f.recommendation
        assert f.config_type == "docker"
