"""Unit tests for email service — payload creation and content verification."""

from unittest.mock import patch

from app.services.email.email_service import (
    _build_payload,
    send_invitation_email,
    send_password_reset_email,
    send_verification_email,
)


class TestBuildPayload:
    def test_sets_correct_fields(self):
        payload = _build_payload("user@test.com", "Test Subject", "<p>Body</p>")
        msg = payload["message"]
        assert msg["subject"] == "Test Subject"
        assert msg["body"]["contentType"] == "HTML"
        assert msg["body"]["content"] == "<p>Body</p>"
        assert msg["toRecipients"][0]["emailAddress"]["address"] == "user@test.com"


class TestSendVerificationEmail:
    @patch("app.services.email.email_service._send")
    def test_includes_token_in_link(self, mock_send):
        send_verification_email("user@test.com", "abc123token", "TestUser")
        mock_send.assert_called_once()
        _, _subject, body = mock_send.call_args[0]
        assert "abc123token" in body

    @patch("app.services.email.email_service._send")
    def test_includes_user_name(self, mock_send):
        send_verification_email("user@test.com", "token", "Jan Kowalski")
        _, _, body = mock_send.call_args[0]
        assert "Jan Kowalski" in body

    @patch("app.services.email.email_service._send")
    def test_subject_is_polish(self, mock_send):
        send_verification_email("user@test.com", "token", "User")
        _, subject, _ = mock_send.call_args[0]
        assert "Aktywacja konta" in subject

    @patch("app.services.email.email_service._send")
    def test_fallback_name_when_empty(self, mock_send):
        send_verification_email("user@test.com", "token", "")
        _, _, body = mock_send.call_args[0]
        assert "Użytkowniku" in body


class TestSendInvitationEmail:
    @patch("app.services.email.email_service._send")
    def test_includes_token_and_company(self, mock_send):
        send_invitation_email("user@test.com", "inv_token", "Admin", "Acme Corp")
        mock_send.assert_called_once()
        _, _subject, body = mock_send.call_args[0]
        assert "inv_token" in body
        assert "Acme Corp" in body
        assert "Admin" in body

    @patch("app.services.email.email_service._send")
    def test_subject_includes_company(self, mock_send):
        send_invitation_email("user@test.com", "token", "Admin", "Firma XYZ")
        _, subject, _ = mock_send.call_args[0]
        assert "Firma XYZ" in subject


class TestSendPasswordResetEmail:
    @patch("app.services.email.email_service._send")
    def test_includes_token_and_name(self, mock_send):
        send_password_reset_email("user@test.com", "reset_token_abc", "Jan")
        mock_send.assert_called_once()
        _, _, body = mock_send.call_args[0]
        assert "reset_token_abc" in body
        assert "Jan" in body

    @patch("app.services.email.email_service._send")
    def test_says_one_hour_not_24(self, mock_send):
        """H2: Password reset email must say 1 hour, not 24 hours."""
        send_password_reset_email("user@test.com", "token", "User")
        _, _, body = mock_send.call_args[0]
        assert "1 godzin" in body
        assert "24 godzin" not in body


class TestSendSkipsWhenNotConfigured:
    def test_send_skips_when_no_oauth_config(self):
        """_send should not raise when MS OAuth is not configured (default config)."""
        from app.services.email.email_service import _send

        # Should not raise — ms_client_id is empty in test config
        _send("x@y.com", "Test", "Body")
