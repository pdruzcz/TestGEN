"""NotificationService — powiadomienia o zbliżaniu się do limitów (Story 7.11).

Zarówno kanał in-app (rekordy ``notifications`` + API odczytu), jak i email
(szablony ``app/templates/email/`` renderowane Jinja2 — jak invoice_service).

Progi (AC1): 80% (warning), 90% (warning), 100% (critical) per zasób.
Zasoby sprawdzane: ``analyses``/``test_cases``/``storage_bytes``
(``files_per_analysis`` jest stateless per analiza — 7.8 — nie jest zużyciem
kumulatywnym, progi nie mają zastosowania). Limit ``None`` = unlimited → skip.

Deduplikacja (AC1/AC4): unique ``(tenant_id, type, resource_type,
threshold_percentage, billing_period)`` — każdy próg danego zasobu wysyłany
raz per okres rozliczeniowy; serwis sprawdza istnienie przed INSERT,
constraint w DB jest backstopem.

Adresat: Owner tenanta (pierwszy po ``created_at`` — user_tenants.role).
Preferencje (AC5): ``users.notification_preferences.limit_warnings``
``{"email": bool, "in_app": bool}`` — domyślnie oba kanały włączone.
Email nieselektywnie best-effort (nie przerywa przebiegu); in_app=false
ukrywa listę i licznik (rekordy dalej powstają — dedup).
"""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.notification import (
    Notification,
    NotificationSeverity,
    NotificationType,
)
from app.models.tenant import Tenant
from app.models.usage import CounterType
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.email.email_service import send_html

logger = logging.getLogger(__name__)

# Progi alertowe (AC1) — kolejność rosnąca; 100% = critical.
THRESHOLDS: tuple[int, ...] = (80, 90, 100)
SEVERITY_BY_THRESHOLD: dict[int, NotificationSeverity] = {
    80: NotificationSeverity.WARNING,
    90: NotificationSeverity.WARNING,
    100: NotificationSeverity.CRITICAL,
}

# Zasoby monitorowane progowo (files_per_analysis — stateless, poza zakresem).
NOTIFICATION_RESOURCES: tuple[CounterType, ...] = (
    CounterType.ANALYSES,
    CounterType.TEST_CASES,
    CounterType.STORAGE_BYTES,
)

# Etykiety PL zasobów do tytułów/treści (AC2: „limit {zasób}").
RESOURCE_DISPLAY: dict[CounterType, str] = {
    CounterType.ANALYSES: "analiz",
    CounterType.TEST_CASES: "przypadków testowych",
    CounterType.STORAGE_BYTES: "dysku",
}

_EMAIL_TEMPLATES: dict[int, str] = {
    80: "limit_warning_80.html",
    90: "limit_warning_90.html",
    100: "limit_reached_100.html",
}

_jinja_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates" / "email"),
    autoescape=select_autoescape(["html"]),
)


def _format_value(resource: CounterType, value: int) -> str:
    """Wartość do wyświetlenia: dysk → GB/MB, liczniki → liczba."""
    if resource == CounterType.STORAGE_BYTES:
        gib = value / 1024**3
        if gib >= 1:
            return f"{gib:.1f} GB"
        return f"{value / 1024**2:.0f} MB"
    return str(int(value))


def render_limit_warning_body(
    *,
    threshold: int,
    resource_display: str,
    current_display: str,
    limit_display: str,
    percentage: int,
    plan_display: str,
    cta_url: str,
) -> str:
    """Treść HTML emaila progowego (AC2) — szablon per próg (Task 4)."""
    template = _EMAIL_TEMPLATES.get(threshold, "limit_warning_80.html")
    return _jinja_env.get_template(template).render(
        resource_display=resource_display,
        current_display=current_display,
        limit_display=limit_display,
        percentage=percentage,
        plan_display=plan_display,
        cta_url=cta_url,
    )


def send_limit_warning_email(
    *,
    to: str,
    subject: str,
    threshold: int,
    resource_display: str,
    current_display: str,
    limit_display: str,
    percentage: int,
    plan_display: str,
    cta_url: str,
) -> None:
    """Email progowy (AC2): temat wg progu + treść z szablonu + CTA upgrade.

    Best-effort — błąd wysyłki logowany, nie przerywa generowania
    powiadomień (wzorzec send_*_email z 7.2/7.4)."""
    try:
        body = render_limit_warning_body(
            threshold=threshold,
            resource_display=resource_display,
            current_display=current_display,
            limit_display=limit_display,
            percentage=percentage,
            plan_display=plan_display,
            cta_url=cta_url,
        )
        send_html(to, subject, body)
    except Exception:
        logger.exception("Email progowy do %s (próg %s%%) nie wysłał się", to, threshold)


def _prefs_enabled(prefs: dict | None, channel: str) -> bool:
    """AC5 — kanał włączony; brak zapisanych preferencji = domyślnie włączony."""
    limit_warnings = (prefs or {}).get("limit_warnings") or {}
    return bool(limit_warnings.get(channel, True))


class NotificationService:
    """Generowanie progowych powiadomień + API odczytu in-app (AC1-AC5)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # --- seam'y pod testy / wstrzykiwanie zależności ---

    async def _get_usage(self, tenant: Tenant) -> dict[str, dict]:
        """Zużycie z limity planu — QuotaService.get_usage (7.8)."""
        from app.services.billing.quota_service import QuotaService

        return await QuotaService(self._db).get_usage(tenant.id)

    async def _get_owner(self, tenant: Tenant) -> User | None:
        """Pierwszy Owner tenanta ( adresat powiadomień, AC1)."""
        result = await self._db.execute(
            select(User)
            .join(UserTenant, UserTenant.user_id == User.id)
            .where(UserTenant.tenant_id == tenant.id, UserTenant.role == TenantRole.OWNER)
            .order_by(UserTenant.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_prefs(self, user_id: uuid.UUID) -> dict | None:
        """Preferencje powiadomień użytkownika (AC5)."""
        result = await self._db.execute(select(User.notification_preferences).where(User.id == user_id))
        return result.scalar_one_or_none()

    # --- generowanie progów (AC1/AC6) ---

    async def check_and_notify_thresholds(self) -> dict:
        """Główna metoda Celery (AC6): każdy aktywny tenant → progi.

        Commit po stronie wywołującego (task Celery). Zwraca statystyki.
        """
        result = await self._db.execute(select(Tenant).where(Tenant.is_active.is_(True)))
        tenants = list(result.scalars().all())

        created = 0
        for tenant in tenants:
            created += len(await self._check_tenant_thresholds(tenant))
        stats = {"tenants": len(tenants), "created": created}
        logger.info("Threshold check: %s", stats)
        return stats

    async def _check_tenant_thresholds(self, tenant: Tenant) -> list[Notification]:
        """Wszystkie nowo osiągnięte progi tenanta (AC1)."""
        owner = await self._get_owner(tenant)
        if owner is None:
            logger.warning("Tenant %s nie ma Ownera — pomijam progi", tenant.id)
            return []

        plan_display = tenant.plan.value.capitalize() if hasattr(tenant.plan, "value") else str(tenant.plan)
        usage = await self._get_usage(tenant)

        created: list[Notification] = []
        for resource in NOTIFICATION_RESOURCES:
            entry = usage.get(resource.value)
            if entry is None or entry.get("limit") is None:
                continue  # unlimited — bez progów
            used, limit = int(entry["used"]), int(entry["limit"])
            if limit <= 0:
                continue
            percentage_raw = used / limit * 100
            for threshold in THRESHOLDS:
                if percentage_raw >= threshold:
                    notification = await self._create_notification(
                        owner, tenant, resource.value, entry, threshold=threshold, plan_display=plan_display
                    )
                    if notification is not None:
                        created.append(notification)
        return created

    async def _create_notification(
        self,
        owner: User,
        tenant: Tenant,
        resource_value: str,
        entry: dict,
        *,
        threshold: int,
        plan_display: str,
    ) -> Notification | None:
        """Rekord powiadomienia z deduplikacją (AC4) + email (AC2).

        ``None`` = próg już obsłużony w tym okresie (dedup).
        """
        resource = CounterType(resource_value)
        used, limit = int(entry["used"]), int(entry["limit"])
        percentage = round(used / limit * 100)
        billing_period = datetime.now(UTC).strftime("%Y-%m")

        existing = await self._db.execute(
            select(Notification.id).where(
                Notification.tenant_id == tenant.id,
                Notification.type == NotificationType.LIMIT_WARNING,
                Notification.resource_type == resource_value,
                Notification.threshold_percentage == threshold,
                Notification.billing_period == billing_period,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None

        resource_display = RESOURCE_DISPLAY[resource]
        reached = threshold >= 100
        title = f"Limit {resource_display} osiągnięty" if reached else f"Zbliżasz się do limitu {resource_display}"
        current_display, limit_display = _format_value(resource, used), _format_value(resource, limit)
        message = (
            f"Osiągnięto limit zasobu {resource_display}: {current_display} z {limit_display} (plan {plan_display})."
            if reached
            else f"Wykorzystujesz {percentage}% limitu zasobu {resource_display}: "
            f"{current_display} z {limit_display} (plan {plan_display})."
        )

        notification = Notification(
            tenant_id=tenant.id,
            user_id=owner.id,
            type=NotificationType.LIMIT_WARNING,
            severity=SEVERITY_BY_THRESHOLD[threshold],
            title=title,
            message=message,
            resource_type=resource_value,
            current_value=used,
            limit_value=limit,
            percentage=percentage,
            threshold_percentage=threshold,
            billing_period=billing_period,
            is_read=False,
            cta_url="/billing/plans",
            meta={"threshold": threshold, "plan": plan_display},
        )
        self._db.add(notification)
        await self._db.flush()

        if _prefs_enabled(owner.notification_preferences, "email"):
            settings = get_settings()
            # Temat wg AC2 — literalnie (mała litera „zbliżasz"), in niż tytuł in-app.
            subject = (
                f"TestGEN — limit {resource_display} osiągnięty"
                if reached
                else f"TestGEN — zbliżasz się do limitu {resource_display}"
            )
            send_limit_warning_email(
                to=owner.email,
                subject=subject,
                threshold=threshold,
                resource_display=resource_display,
                current_display=current_display,
                limit_display=limit_display,
                percentage=percentage,
                plan_display=plan_display,
                cta_url=f"{settings.frontend_base_url}/billing/plans",
            )
        return notification

    # --- odczyt in-app (AC3/AC5) ---

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        """Liczba nieprzeczytanych (badge dzwonka); in_app=false → 0."""
        if not _prefs_enabled(await self._get_prefs(user_id), "in_app"):
            return 0
        result = await self._db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return int(result.scalar_one_or_none() or 0)

    async def get_notifications(
        self, user_id: uuid.UUID, page: int = 1, size: int = 20
    ) -> tuple[list[Notification], int]:
        """Lista z paginacją (najnowsze pierwsze); in_app=false → pusta."""
        if not _prefs_enabled(await self._get_prefs(user_id), "in_app"):
            return [], 0
        conditions = (Notification.user_id == user_id,)
        items_result = await self._db.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        total_result = await self._db.execute(select(func.count()).select_from(Notification).where(*conditions))
        return list(items_result.scalars().all()), int(total_result.scalar_one_or_none() or 0)

    async def mark_as_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
        """Oznacz jako przeczytane (AC3) — tylko własne powiadomienia."""
        result = await self._db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundError("Notification not found")
        notification.is_read = True
        await self._db.flush()
        return notification

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """„Oznacz wszystkie jako przeczytane" (AC3) — liczba zmienionych."""
        result = await self._db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()
        return result.rowcount or 0
