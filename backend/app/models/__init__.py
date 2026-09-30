from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode
from app.models.anonymization_map import AnonymizationMap
from app.models.api_key import ApiKey, ApiKeyScope, ApiKeyStatus
from app.models.audit_log import AuditLog
from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from app.models.code_error import CodeError, ErrorCategory
from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.email_verification import EmailVerification, VerificationType
from app.models.gap_finding import GapFinding, GapType
from app.models.gherkin_feature import GherkinFeature, GherkinStatus
from app.models.gui_screenshot import (
    GUIAnalysisResult,
    GUIAnalysisStatus,
    GUIComponent,
    GUIComponentType,
    GUIScreenshot,
)
from app.models.healing_report import (
    HealingItem,
    HealingReport,
    HealingStatus,
    LocatorStrategy,
)
from app.models.integration import (
    IntegrationConfig,
    IntegrationEvent,
    IntegrationProvider,
    IntegrationSyncLog,
    ScmEventStatus,
    ScmEventType,
    ScmIntegration,
    ScmProvider,
    SyncStatus,
)
from app.models.invoice import Invoice, InvoicePaymentMethod, InvoiceStatus
from app.models.invoice_data import InvoiceData
from app.models.jira_import import JiraImport, JiraImportStatus
from app.models.llm_usage import LLMUsage
from app.models.mfa import UserMFA
from app.models.notification import Notification, NotificationSeverity, NotificationType
from app.models.outbound_webhook import (
    DeliveryStatus,
    OutboundWebhook,
    WebhookDelivery,
    WebhookEventType,
)
from app.models.payment import (
    PaymentStatus,
    PaymentToken,
    PaymentTransaction,
    TokenKind,
    TpayTokenStatus,
    WebhookEvent,
    WebhookProcessingStatus,
)
from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
from app.models.platform_setting import PlatformSetting
from app.models.project import Project, ProjectStatus
from app.models.recommendation import Recommendation, RecommendationPriority
from app.models.report import Report, ReportFormat
from app.models.security_finding import (
    AnalysisSource,
    CVEDatabase,
    FindingStatus,
    ScanStatus,
    ScanType,
    SecurityFinding,
    SecurityScan,
    Severity,
)
from app.models.source_file import SourceFile
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.sync_conflict import ConflictResolution, SyncConflict
from app.models.sync_state import (
    ConflictStrategy,
    SyncDirection,
    SyncHealth,
    SyncState,
)
from app.models.tenant import PlanType, Tenant
from app.models.test_case import TestCase, TestPriority, TestType
from app.models.test_code import TestCode
from app.models.traceability import CoverageStatus, TraceabilityMatrix
from app.models.uml_diagram import (
    DiagramType,
    ParsedUMLModel,
    UMLDiagram,
    UMLDiagramStatus,
    UMLFormat,
)
from app.models.usage import CounterType, UsageCounter
from app.models.usage_history import UsageHistory
from app.models.user import User
from app.models.user_flow import FlowSourceType, FlowStatus, FlowStep, UserFlow
from app.models.user_tenant import TenantRole, UserTenant
from app.models.visual_regression import ComparisonStatus, VisualRegressionResult

__all__ = [
    "AnalysisResult",
    "AnalysisSource",
    "AnalysisStatus",
    "AnonymizationMap",
    "ApiKey",
    "ApiKeyScope",
    "ApiKeyStatus",
    "AuditLog",
    "Base",
    "CVEDatabase",
    "CodeError",
    "ComparisonStatus",
    "ComplianceSnapshot",
    "ConflictResolution",
    "ConflictStrategy",
    "CounterType",
    "CoverageStatus",
    "DeliveryStatus",
    "DiagramType",
    "EmailVerification",
    "EngineMode",
    "ErrorCategory",
    "FindingStatus",
    "FlowSourceType",
    "FlowStatus",
    "FlowStep",
    "GUIAnalysisResult",
    "GUIAnalysisStatus",
    "GUIComponent",
    "GUIComponentType",
    "GUIScreenshot",
    "GapFinding",
    "GapType",
    "GherkinFeature",
    "GherkinStatus",
    "HealingItem",
    "HealingReport",
    "HealingStatus",
    "IntegrationConfig",
    "IntegrationEvent",
    "IntegrationProvider",
    "IntegrationSyncLog",
    "Invoice",
    "InvoiceData",
    "InvoicePaymentMethod",
    "InvoiceStatus",
    "JiraImport",
    "JiraImportStatus",
    "LLMUsage",
    "LocatorStrategy",
    "Notification",
    "NotificationSeverity",
    "NotificationType",
    "OutboundWebhook",
    "ParsedUMLModel",
    "PaymentStatus",
    "PaymentToken",
    "PaymentTransaction",
    "PlanChangeHistory",
    "PlanChangeStatus",
    "PlanChangeType",
    "PlanName",
    "PlanType",
    "PlatformSetting",
    "Project",
    "ProjectStatus",
    "Recommendation",
    "RecommendationPriority",
    "Report",
    "ReportFormat",
    "ScanStatus",
    "ScanType",
    "ScmEventStatus",
    "ScmEventType",
    "ScmIntegration",
    "ScmProvider",
    "SecurityFinding",
    "SecurityScan",
    "Severity",
    "SourceFile",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "SyncConflict",
    "SyncDirection",
    "SyncHealth",
    "SyncState",
    "SyncStatus",
    "Tenant",
    "TenantMixin",
    "TenantRole",
    "TestCase",
    "TestCode",
    "TestPriority",
    "TestType",
    "TimestampMixin",
    "TokenKind",
    "TpayTokenStatus",
    "TraceabilityMatrix",
    "UMLDiagram",
    "UMLDiagramStatus",
    "UMLFormat",
    "UUIDMixin",
    "UsageCounter",
    "UsageHistory",
    "User",
    "UserFlow",
    "UserMFA",
    "UserTenant",
    "VerificationType",
    "VisualRegressionResult",
    "WebhookDelivery",
    "WebhookEvent",
    "WebhookEventType",
    "WebhookProcessingStatus",
]


def get_all_models() -> list[type]:
    """Return all model classes for Alembic autogenerate."""
    return [
        AnalysisResult,
        AnonymizationMap,
        ApiKey,
        AuditLog,
        CodeError,
        ComplianceSnapshot,
        EmailVerification,
        GapFinding,
        GherkinFeature,
        HealingItem,
        HealingReport,
        IntegrationConfig,
        IntegrationEvent,
        IntegrationSyncLog,
        Invoice,
        InvoiceData,
        Notification,
        OutboundWebhook,
        PlatformSetting,
        Recommendation,
        GUIAnalysisResult,
        GUIComponent,
        GUIScreenshot,
        LLMUsage,
        PaymentToken,
        PaymentTransaction,
        PlanChangeHistory,
        Project,
        Report,
        CVEDatabase,
        ScmIntegration,
        SecurityFinding,
        SecurityScan,
        SourceFile,
        Subscription,
        SubscriptionPlan,
        Tenant,
        UsageCounter,
        UsageHistory,
        TestCase,
        TestCode,
        TraceabilityMatrix,
        WebhookDelivery,
        WebhookEvent,
        UMLDiagram,
        ParsedUMLModel,
        User,
        UserFlow,
        FlowStep,
        UserMFA,
        UserTenant,
        VisualRegressionResult,
    ]
