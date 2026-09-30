"""Tests for audit services - Stories 1.47, 1.48"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.audit_log import AuditEventType
from app.services.audit import (
    AlertSeverity,
    AlertType,
    AuditContext,
    AuditLogger,
    AuditSeverity,
    LogRetentionService,
    RetentionPeriod,
    SecurityAlert,
)


class TestAuditSeverity:
    """Test AuditSeverity enum."""

    def test_severity_values(self):
        assert AuditSeverity.LOW == "low"
        assert AuditSeverity.MEDIUM == "medium"
        assert AuditSeverity.HIGH == "high"
        assert AuditSeverity.CRITICAL == "critical"


class TestAuditLogger:
    """Test audit logger (Story 1.47)."""

    def test_logger_initialization(self):
        logger = AuditLogger()
        assert logger is not None

    def test_log_authentication_event(self):
        logger = AuditLogger()
        context = AuditContext(
            user_id=uuid4(),
            ip_address="127.0.0.1",
        )
        # Test log call doesn't raise
        logger.log_authentication(
            actor_id=uuid4(),
            action="login_success",
            context=context,
        )


class TestLogRetentionService:
    """Test log retention service (Story 1.48)."""

    def test_service_initialization(self):
        service = LogRetentionService()
        assert service is not None
        assert service.retention_policies is not None
        assert service.alert_thresholds is not None

    def test_retention_policies(self):
        service = LogRetentionService()
        assert len(service.retention_policies) > 0

    def test_alert_thresholds(self):
        service = LogRetentionService()
        assert "max_failed_logins" in service.alert_thresholds
        assert service.alert_thresholds["max_failed_logins"] == 10

    def test_cutoff_date_calculation(self):
        service = LogRetentionService()
        cutoff = service._get_cutoff_date(RetentionPeriod.DAYS_30)
        expected = datetime.utcnow() - timedelta(days=30)
        assert (cutoff - expected).total_seconds() < 60  # Within 1 minute


class TestSecurityAlert:
    """Test SecurityAlert dataclass."""

    def test_alert_creation(self):
        alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE,
            severity=AlertSeverity.CRITICAL,
            title="Brute force detected",
            description="Multiple failed logins",
            detected_at=datetime.utcnow(),
            related_events=[],
        )

        assert alert.alert_type == AlertType.BRUTE_FORCE
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.resolved is False
