"""Unit tests for XSS remediation templates — Story 4.9."""

import app.services.security_scan.recommendation_templates  # noqa: F401 — registers templates
from app.services.security_scan.recommendation_templates.registry import TemplateRegistry


class TestXssTemplates:
    def test_registered(self):
        assert TemplateRegistry.has("xss")

    def test_react_dompurify(self):
        t = TemplateRegistry.get_template("xss", "javascript", "react")
        assert "DOMPurify" in t.fixed_code_snippet

    def test_vue_v_text(self):
        t = TemplateRegistry.get_template("xss", "javascript", "vue")
        assert "v-text" in t.fixed_code_snippet

    def test_django_escape(self):
        t = TemplateRegistry.get_template("xss", "python", "django")
        assert "escape" in t.fixed_code_snippet

    def test_flask_markupsafe(self):
        t = TemplateRegistry.get_template("xss", "python", "flask")
        assert "escape" in t.fixed_code_snippet.lower()

    def test_jsp_c_out(self):
        t = TemplateRegistry.get_template("xss", "java", "jsp")
        assert "c:out" in t.fixed_code_snippet

    def test_generic_fallback(self):
        t = TemplateRegistry.get_template("xss", "rust")
        assert t is not None
