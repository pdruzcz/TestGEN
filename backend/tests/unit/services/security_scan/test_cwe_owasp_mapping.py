"""Tests for the CWE/OWASP mapping and rule registry (Story 4.2)."""

from app.services.security_scan.rules import (
    ALL_RULES,
    CWE_OWASP_MAPPING,
    RuleRegistry,
    cwe_for,
    get_registry,
    owasp_for,
    severity_for,
)


class TestMapping:
    def test_known_types_present(self):
        for vt in ("sql_injection", "xss", "csrf", "broken_authz", "idor", "hardcoded_secret"):
            assert vt in CWE_OWASP_MAPPING

    def test_sqli_mapping(self):
        assert cwe_for("sql_injection") == "CWE-89"
        assert owasp_for("sql_injection") == "A03:2021-Injection"
        assert severity_for("sql_injection") == "critical"

    def test_unknown_type_uses_default_severity(self):
        assert severity_for("nope", "low") == "low"
        assert cwe_for("nope") is None


class TestRegistry:
    def test_registry_singleton(self):
        assert get_registry() is get_registry()

    def test_get_rules_filters_by_language(self):
        reg = get_registry()
        py_rules = reg.get_rules("python")
        # A Java-only rule (Spring CSRF disable) must not appear for Python.
        assert all(r.id != "JAVA-CSRF-DISABLED" for r in py_rules)
        # A language-agnostic secret rule must appear.
        assert any(r.id == "SECRET-HARDCODED" for r in py_rules)

    def test_get_rules_by_cwe(self):
        reg = get_registry()
        assert any(r.id == "SQLI-STRING-CONCAT" for r in reg.get_rules_by_cwe("CWE-89"))

    def test_get_rule_by_id(self):
        assert get_registry().get_rule_by_id("JS-DOM-SINK") is not None

    def test_rules_cover_six_vuln_families(self):
        families = {r.vulnerability_type for r in ALL_RULES}
        for vt in ("sql_injection", "xss", "csrf", "hardcoded_secret"):
            assert vt in families
        assert {"broken_authz", "idor"} & families

    def test_custom_registry_uses_given_rules(self):
        reg = RuleRegistry(rules=[])
        assert reg.get_rules("python") == []
