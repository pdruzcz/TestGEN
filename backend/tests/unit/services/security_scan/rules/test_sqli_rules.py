"""SQL injection rule tests (Story 4.2) — per language."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_python_cursor_fstring():
    assert "sql_injection" in _types('cursor.execute(f"SELECT * FROM u WHERE id={i}")\n', "python")


def test_python_string_concat():
    assert "sql_injection" in _types('q = "SELECT * FROM u WHERE id=" + uid\n', "python")


def test_java_statement_concat():
    code = 'st.executeQuery("SELECT * FROM accounts WHERE id = \'" + userId + "\'");\n'
    assert "sql_injection" in _types(code, "java")


def test_js_query_template_literal():
    assert "sql_injection" in _types("db.query(`SELECT * FROM u WHERE id=${id}`)\n", "javascript")


def test_csharp_sqlcommand_concat():
    assert "sql_injection" in _types('var c = new SqlCommand("SELECT * FROM u WHERE id=" + id);\n', "csharp")


def test_parametrized_query_not_flagged():
    assert "sql_injection" not in _types('cursor.execute("SELECT * FROM u WHERE id=%s", (uid,))\n', "python")


def test_cwe_and_owasp_on_finding():
    findings = engine.scan_code('cursor.execute(f"SELECT * FROM u WHERE id={i}")\n', "python", "f")
    sqli = next(f for f in findings if f.vulnerability_type == "sql_injection")
    assert sqli.cwe_id == "CWE-89"
    assert sqli.owasp_category == "A03:2021-Injection"
    assert sqli.severity == "critical"
