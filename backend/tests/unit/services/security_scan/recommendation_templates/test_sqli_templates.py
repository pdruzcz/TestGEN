"""Unit tests for SQLi remediation templates — Story 4.9."""

import app.services.security_scan.recommendation_templates  # noqa: F401 — registers templates
from app.services.security_scan.recommendation_templates.registry import TemplateRegistry


class TestSqliTemplates:
    def test_registered(self):
        assert TemplateRegistry.has("sql_injection")

    def test_python_default(self):
        t = TemplateRegistry.get_template("sql_injection", "python")
        assert t is not None
        assert "%s" in t.fixed_code_snippet
        assert t.language == "python"

    def test_python_sqlalchemy_framework(self):
        t = TemplateRegistry.get_template("sql_injection", "python", "sqlalchemy")
        assert "session.query" in t.fixed_code_snippet

    def test_java_jdbc(self):
        t = TemplateRegistry.get_template("sql_injection", "java", "jdbc")
        assert "PreparedStatement" in t.fixed_code_snippet

    def test_node(self):
        t = TemplateRegistry.get_template("sql_injection", "javascript", "node")
        assert "pool.query" in t.fixed_code_snippet

    def test_csharp_ef(self):
        t = TemplateRegistry.get_template("sql_injection", "csharp", "ef")
        assert "context.Users" in t.fixed_code_snippet

    def test_unknown_language_falls_back(self):
        t = TemplateRegistry.get_template("sql_injection", "rust")
        assert t is not None  # graceful degradation to generic / any language

    def test_unknown_framework_falls_back_to_language_default(self):
        t = TemplateRegistry.get_template("sql_injection", "python", "no_such_orm")
        assert t is not None
        assert t.language == "python"
