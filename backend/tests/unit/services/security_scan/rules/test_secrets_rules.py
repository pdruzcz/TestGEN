"""Hardcoded secret rule tests (Story 4.2)."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_hardcoded_password():
    assert "hardcoded_secret" in _types('password = "hunter2secret"\n', "python")


def test_hardcoded_api_key():
    assert "hardcoded_secret" in _types('api_key = "sk_live_abcdef123456"\n', "javascript")


def test_private_key_block():
    assert "hardcoded_secret" in _types("-----BEGIN RSA PRIVATE KEY-----\n", "python")


def test_aws_access_key():
    assert "hardcoded_secret" in _types('aws = "AKIAIOSFODNN7EXAMPLE"\n', "python")


def test_jwt_literal():
    code = 'const t = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVC9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123"\n'
    assert "hardcoded_secret" in _types(code, "javascript")


def test_secret_cwe_mapping():
    findings = engine.scan_code('password = "hunter2secret"\n', "python", "f")
    secret = next(f for f in findings if f.vulnerability_type == "hardcoded_secret")
    assert secret.cwe_id == "CWE-798"


def test_non_secret_assignment_not_flagged():
    assert "hardcoded_secret" not in _types('name = "Alice"\n', "python")
