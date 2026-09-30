"""
Audit log service - Story 1.47

Logs sensitive operations for compliance:
- User authentication events
- Project access control
- Data export operations
- Test execution results
- Configuration changes
- Admin actions
- Data deletion

Provides audit trail for security and compliance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.core.database import get_sync_session
from app.models.audit_log import AuditEvent, AuditEventType

logger = logging.getLogger(__name__)


class AuditSeverity(StrEnum):
    """Severity level of audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditContext:
    """Context information for audit events."""
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    project_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] | None = None


class AuditLogger:
    """Service for logging audit events."""

    def __init__(self):
        pass

    def log_event(
        self,
        event_type: AuditEventType,
        actor_id: UUID | None,
        actor_type: str | None,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        context: AuditContext | None = None,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        """
        Log an audit event.

        Args:
            event_type: Type of audit event
            actor_id: ID of user/system performing action
            actor_type: Type of actor (user, system, api)
            action: Description of action performed
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            context: Additional context
            severity: Event severity
            details: Additional details

        Returns:
            Created AuditEvent or None if failed
        """
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                event = AuditEvent(
                    actor_id=actor_id,
                    actor_type=actor_type or "system",
                    action=action,
                    event_type=event_type,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    severity=severity,
                    details=details or {},
                    ip_address=context.ip_address if context else None,
                    user_agent=context.user_agent if context else None,
                    session_id=context.session_id if context else None,
                    request_id=context.request_id if context else None,
                    metadata=context.metadata if context else None,
                )

                db.add(event)
                db.commit()
                db.refresh(event)

                logger.info(f"Audit event logged: {event_type.value} - {action}")
                return event

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return None

    def log_authentication(
        self,
        actor_id: UUID | None,
        action: str,  # "login_success", "login_failed", "logout", "mfa_enabled"
        context: AuditContext | None = None,
    ) -> AuditEvent | None:
        """Log authentication events."""
        return self.log_event(
            event_type=AuditEventType.AUTHENTICATION,
            actor_id=actor_id,
            actor_type="user",
            action=action,
            context=context,
            severity=AuditSeverity.HIGH if "login_success" in action else AuditSeverity.MEDIUM,
        )

    def log_authorization(
        self,
        actor_id: UUID | None,
        action: str,  # "access_granted", "access_denied", "permission_checked"
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        context: AuditContext | None = None,
    ) -> AuditEvent | None:
        """Log authorization events."""
        return self.log_event(
            event_type=AuditEventType.AUTHORIZATION,
            actor_id=actor_id,
            actor_type="user",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
        )

    def log_data_export(
        self,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        export_format: str,
        record_count: int,
        context: AuditContext | None = None,
    ) -> AuditEvent | None:
        """Log data export events."""
        return self.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            actor_id=actor_id,
            actor_type="user",
            action=f"Exported {record_count} {resource_type} records as {export_format}",
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
            severity=AuditSeverity.MEDIUM,
            details={"export_format": export_format, "record_count": record_count},
        )

    def log_data_deletion(
        self,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        deletion_reason: str,
        context: AuditContext | None = None,
    ) -> AuditEvent | None:
        """Log data deletion events."""
        return self.log_event(
            event_type=AuditEventType.DATA_DELETION,
            actor_id=actor_id,
            actor_type="user",
            action=f"Deleted {resource_type} - {deletion_reason}",
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
            severity=AuditSeverity.HIGH,
            details={"deletion_reason": deletion_reason},
        )

    def log_configuration_change(
        self,
        actor_id: UUID | None,
        config_key: str,
        old_value: Any | None,
        new_value: Any | None,
        context: AuditContext | None = None,
    ) -> AuditEvent | None:
        """Log configuration changes."""
        return self.log_event(
            event_type=AuditEventType.CONFIGURATION_CHANGE,
            actor_id=actor_id,
            actor_type="user",
            action=f"Changed config: {config_key}",
            context=context,
            severity=AuditSeverity.MEDIUM,
            details={"config_key": config_key, "old_value": str(old_value), "new_value": str(new_value)},
        )


def get_audit_logger() -> AuditLogger:
    """Get or create audit logger instance."""
    return AuditLogger()
