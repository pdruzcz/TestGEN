"""Input validation / injection rule tests (Story 4.2)."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_python_os_system():
    assert "command_injection" in _types("os.system('ls ' + path)\n", "python")


def test_python_subprocess_shell_true():
    assert "command_injection" in _types("subprocess.run(cmd, shell=True)\n", "python")


def test_js_child_process_exec():
    assert "command_injection" in _types("cp.exec(`tar -czf ${name}.tar.gz`)\n", "javascript")


def test_python_eval():
    assert "code_injection" in _types("v = eval(expr)\n", "python")


def test_js_new_function():
    assert "code_injection" in _types("const f = new Function(body);\n", "javascript")


def test_path_traversal_open_concat():
    assert "path_traversal" in _types("open('/data/' + name)\n", "python")


def test_python_pickle_loads():
    assert "insecure_deserialization" in _types("obj = pickle.loads(blob)\n", "python")


def test_weak_hash_md5():
    assert "weak_cryptography" in _types("h = hashlib.md5(data).hexdigest()\n", "python")


def test_command_injection_cwe():
    findings = engine.scan_code("os.system('ls ' + path)\n", "python", "f")
    ci = next(f for f in findings if f.vulnerability_type == "command_injection")
    assert ci.cwe_id == "CWE-78"
    assert ci.severity == "critical"
