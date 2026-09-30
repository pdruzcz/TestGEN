"""Log retention and security alerts service - Story 1.48

Manages log retention policies and security alerts:
- Automatic log cleanup based on retention policies
- Security event detection and alerting
- Anomaly detection in audit logs
- Compliance reporting
- Log archiving

Ensures logs are retained appropriately and security events are flagged.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.core.database import get_sync_session
from app.models.audit_log import AuditEvent, AuditEventType

logger = logging.getLogger(__name__)


class RetentionPeriod(StrEnum):
    """Log retention periods."""
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    DAYS_180 = "180d"
    DAYS_365 = "365d"
    DAYS_730 = "730d"  # 2 years
    PERMANENT = "permanent"


class AlertSeverity(StrEnum):
    """Security alert severity."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(StrEnum):
    """Types of security alerts."""
    BRUTE_FORCE = "brute_force"  # Multiple failed logins
    PRIVILEGE_ESCALATION = "privilege_escalation"  # Unusual admin access
    DATA_EXFILTRATION = "data_exfiltration"  # Large data exports
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # Access denied spikes
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"  # Unusual patterns
    COMPLIANCE_VIOLATION = "compliance_violation"  # Policy violations


@dataclass
class RetentionPolicy:
    """Log retention policy for event types."""
    event_type: AuditEventType
    retention_period: RetentionPeriod
    archive_after_retention: bool = False


@dataclass
class SecurityAlert:
    """A security alert generated from log analysis."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    detected_at: datetime
    related_events: list[UUID]
    details: dict[str, Any] | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None


class LogRetentionService:
    """Service for log retention and security monitoring."""

    def __init__(self):
        self.retention_policies = self._get_default_policies()
        self.alert_thresholds = self._get_alert_thresholds()

    def cleanup_old_logs(
        self, dry_run: bool = False
    ) -> dict[str, int]:
        """
        Clean up logs based on retention policies.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {"total_deleted": 0, "by_event_type": {}}

        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                for policy in self.retention_policies:
                    cutoff_date = self._get_cutoff_date(policy.retention_period)

                    # Count matching events
                    events_to_delete = (
                        db.query(AuditEvent)
                        .filter(
                            AuditEvent.event_type == policy.event_type,
                            AuditEvent.created_at < cutoff_date,
                        )
                        .all()
                    )

                    count = len(events_to_delete)
                    stats["by_event_type"][policy.event_type.value] = count
                    stats["total_deleted"] += count

                    # Delete if not dry run
                    if not dry_run and count > 0:
                        for event in events_to_delete:
                            db.delete(event)
                        db.commit()

                logger.info(f"Log cleanup complete: {stats['total_deleted']} events deleted")

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")

        return stats

    def analyze_security_events(
        self, lookback_days: int = 7
    ) -> list[SecurityAlert]:
        """
        Analyze recent events for security concerns.

        Args:
            lookback_days: Number of days to look back

        Returns:
            List of security alerts
        """
        alerts = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                # Get recent events
                recent_events = (
                    db.query(AuditEvent)
                    .filter(AuditEvent.created_at >= cutoff_date)
                    .order_by(AuditEvent.created_at)
                    .all()
                )

                # Check for brute force patterns
                brute_force_alerts = self._detect_brute_force(recent_events)
                alerts.extend(brute_force_alerts)

                # Check for data exfiltration
                exfil_alerts = self._detect_data_exfiltration(recent_events)
                alerts.extend(exfil_alerts)

                # Check for unauthorized access attempts
                access_alerts = self._detect_unauthorized_access(recent_events)
                alerts.extend(access_alerts)

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Security analysis failed: {e}")

        return alerts

    def get_retention_stats(self) -> dict[str, Any]:
        """Get statistics about log retention."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                total_count = db.query(AuditEvent).count()

                # Count by event type
                from sqlalchemy import func
                type_counts = (
                    db.query(AuditEvent.event_type, func.count(AuditEvent.id))
                    .group_by(AuditEvent.event_type)
                    .all()
                )

                by_type = {event_type.value: count for event_type, count in type_counts}

                # Oldest and newest events
                oldest = (
                    db.query(AuditEvent)
                    .order_by(AuditEvent.created_at)
                    .first()
                )
                newest = (
                    db.query(AuditEvent)
                    .order_by(AuditEvent.created_at.desc())
                    .first()
                )

                return {
                    "total_events": total_count,
                    "by_event_type": by_type,
                    "oldest_event": oldest.created_at if oldest else None,
                    "newest_event": newest.created_at if newest else None,
                    "retention_policies": len(self.retention_policies),
                }

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to get retention stats: {e}")
            return {}

    def _detect_brute_force(
        self, events: list[AuditEvent]
    ) -> list[SecurityAlert]:
        """Detect potential brute force attacks."""
        alerts = []

        # Count failed logins per IP
        failed_logins_by_ip = {}
        for event in events:
            if (
                event.event_type == AuditEventType.AUTHENTICATION
                and "login_failed" in event.action
            ):
                ip = event.ip_address or "unknown"
                failed_logins_by_ip[ip] = failed_logins_by_ip.get(ip, 0) + 1

        # Alert on IPs with many failed attempts
        for ip, count in failed_logins_by_ip.items():
            if count >= self.alert_thresholds["max_failed_logins"]:
                alerts.append(
                    SecurityAlert(
                        alert_type=AlertType.BRUTE_FORCE,
                        severity=AlertSeverity.CRITICAL if count > 20 else AlertSeverity.WARNING,
                        title=f"Potential brute force from {ip}",
                        description=f"{count} failed login attempts from {ip}",
                        detected_at=datetime.utcnow(),
                        related_events=[],
                        details={"ip_address": ip, "attempt_count": count},
                    )
                )

        return alerts

    def _detect_data_exfiltration(
        self, events: list[AuditEvent]
    ) -> list[SecurityAlert]:
        """Detect potential data exfiltration."""
        alerts = []

        # Check for unusually large exports
        for event in events:
            if event.event_type == AuditEventType.DATA_EXPORT:
                record_count = event.details.get("record_count", 0)
                if record_count >= self.alert_thresholds["max_export_records"]:
                    alerts.append(
                        SecurityAlert(
                            alert_type=AlertType.DATA_EXFILTRATION,
                            severity=AlertSeverity.WARNING,
                            title=f"Large data export by {event.actor_id}",
                            description=f"Exported {record_count} records",
                            detected_at=datetime.utcnow(),
                            related_events=[event.id],
                            details={"record_count": record_count, "actor": str(event.actor_id)},
                        )
                    )

        return alerts

    def _detect_unauthorized_access(
        self, events: list[AuditEvent]
    ) -> list[SecurityAlert]:
        """Detect unusual unauthorized access patterns."""
        alerts = []

        # Count access denied per user
        denied_by_user = {}
        for event in events:
            if (
                event.event_type == AuditEventType.AUTHORIZATION
                and "access_denied" in event.action
            ):
                user = str(event.actor_id) if event.actor_id else "unknown"
                denied_by_user[user] = denied_by_user.get(user, 0) + 1

        # Alert on users with many denied attempts
        for user, count in denied_by_user.items():
            if count >= self.alert_thresholds["max_access_denied"]:
                alerts.append(
                    SecurityAlert(
                        alert_type=AlertType.UNAUTHORIZED_ACCESS,
                        severity=AlertSeverity.WARNING,
                        title=f"Multiple unauthorized access attempts by {user}",
                        description=f"{count} access denied events",
                        detected_at=datetime.utcnow(),
                        related_events=[],
                        details={"user": user, "attempt_count": count},
                    )
                )

        return alerts

    def _get_cutoff_date(self, retention_period: RetentionPeriod) -> datetime:
        """Get cutoff date for retention period."""
        periods = {
            RetentionPeriod.DAYS_30: 30,
            RetentionPeriod.DAYS_90: 90,
            RetentionPeriod.DAYS_180: 180,
            RetentionPeriod.DAYS_365: 365,
            RetentionPeriod.DAYS_730: 730,
            RetentionPeriod.PERMANENT: 365 * 10,  # 10 years for practical purposes
        }
        days = periods.get(retention_period, 365)
        return datetime.utcnow() - timedelta(days=days)

    def _get_default_policies(self) -> list[RetentionPolicy]:
        """Get default retention policies."""
        return [
            # Security events: longer retention
            RetentionPolicy(
                AuditEventType.AUTHENTICATION, RetentionPeriod.DAYS_730
            ),
            RetentionPolicy(
                AuditEventType.AUTHORIZATION, RetentionPeriod.DAYS_365
            ),
            # Data operations: medium retention
            RetentionPolicy(
                AuditEventType.DATA_EXPORT, RetentionPeriod.DAYS_180
            ),
            RetentionPolicy(
                AuditEventType.DATA_DELETION, RetentionPeriod.DAYS_365
            ),
            # Configuration changes: shorter retention
            RetentionPolicy(
                AuditEventType.CONFIGURATION_CHANGE, RetentionPeriod.DAYS_90
            ),
            # Admin actions: long retention
            RetentionPolicy(AuditEventType.ADMIN_ACTION, RetentionPeriod.DAYS_730),
        ]

    def _get_alert_thresholds(self) -> dict[str, int]:
        """Get alert detection thresholds."""
        return {
            "max_failed_logins": 10,
            "max_export_records": 10000,
            "max_access_denied": 20,
        }


def get_log_retention_service() -> LogRetentionService:
    """Get or create log retention service instance."""
    return LogRetentionService()
