import logging

from celery import Celery, signals
from celery.schedules import crontab
from kombu import Queue

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "testgen",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer=settings.celery_task_serializer,
    accept_content=settings.celery_accept_content,
    result_serializer=settings.celery_result_serializer,
    timezone=settings.celery_timezone,
    enable_utc=True,
    # Execution
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Time limits (defaults — overridden per-task when needed)
    task_soft_time_limit=settings.celery_soft_time_limit,
    task_time_limit=settings.celery_hard_time_limit,
    # Queues
    task_queues=(
        Queue("default"),
        Queue("analysis"),
        Queue("export"),
        Queue("security"),
        Queue("email"),
        # Story 8.7: dostawy webhooków wychodzących — oddzielone, żeby
        # zablokowany endpoint klienta nie wstrzymywał analiz.
        Queue("webhooks"),
        # Story 8.11: dwukierunkowa synchronizacja z TMS — oddzielona od
        # ``export``, bo eksport uruchamia użytkownik i czeka na wynik,
        # a kwadransowy cykl synchronizacji stałby mu na drodze.
        Queue("sync"),
    ),
    task_default_queue="default",
    # Task routing — map module prefixes to dedicated queues
    task_routes={
        "app.workers.tasks.analysis_tasks.*": {"queue": "analysis"},
        "analysis.run_pipeline": {"queue": "analysis"},
        "app.workers.tasks.export_tasks.*": {"queue": "export"},
        "export.testrail": {"queue": "export"},
        "export.jira_tms": {"queue": "export"},
        "app.workers.tasks.security_tasks.*": {"queue": "security"},
        "app.workers.tasks.email_tasks.*": {"queue": "email"},
        "integrations.run_webhook_analysis": {"queue": "analysis"},
        "integrations.finalize_webhook_status": {"queue": "analysis"},
        "integrations.fail_webhook_status": {"queue": "analysis"},
        "webhooks.deliver": {"queue": "webhooks"},
        "webhooks.retry_pending": {"queue": "webhooks"},
        "sync.scan_due": {"queue": "sync"},
        "sync.run": {"queue": "sync"},
        "jira.import_requirements": {"queue": "sync"},
    },
)

# Beat schedule — periodic background jobs.
celery_app.conf.beat_schedule = {
    "cleanup-source-files-daily": {
        "task": "app.workers.tasks.cleanup_tasks.cleanup_source_files",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "default"},
    },
    "cve-update-database-monthly": {
        "task": "security.update_cve_database",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
        "options": {"queue": "security"},
    },
    # Story 7.2 (AC5/AC6) — odnowienia cykliczne + dunning + wygasłe grace;
    # 03:30 (po cleanupie 02:00, przed godzinnym szczytem).
    "billing-subscription-renewals-daily": {
        "task": "app.workers.tasks.billing_tasks.run_subscription_renewals",
        "schedule": crontab(hour=3, minute=30),
        "options": {"queue": "default"},
    },
    # Story 7.9 (AC3) — daily snapshot liczników do usage_history (00:00,
    # przed renewals 03:30 — snapshot dnia zamyka się przed zmianą okresu).
    "billing-usage-snapshot-daily": {
        "task": "app.workers.tasks.usage_snapshot.run_usage_snapshot",
        "schedule": crontab(hour=0, minute=0),
        "options": {"queue": "default"},
    },
    # Story 7.11 (AC6) — hourly sprawdzanie progów zużycia 80/90/100% →
    # powiadomienia in-app + email (dedup per okres w NotificationService).
    "billing-check-thresholds-hourly": {
        "task": "app.workers.tasks.check_thresholds.check_usage_thresholds",
        "schedule": crontab(minute=0),
        "options": {"queue": "default"},
    },
    # Story 8.7 (AC4) — siatka bezpieczeństwa dla ponowień: zadania z
    # ``countdown`` giną przy restarcie brokera, wiersze w bazie nie.
    "webhooks-retry-pending-every-minute": {
        "task": "webhooks.retry_pending",
        "schedule": crontab(minute="*"),
        "options": {"queue": "webhooks"},
    },
    # Story 8.11 (AC2/AC3) — co 5 minut szukamy zaległych synchronizacji.
    # Odstęp skanu jest zarazem minimalnym odstępem synchronizacji: częstszy
    # skan nic by nie dał, bo krótszego cyklu i tak nie da się ustawić.
    "tms-sync-scan-due-every-5-minutes": {
        "task": "sync.scan_due",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "sync"},
    },
}

celery_app.autodiscover_tasks(["app.workers.tasks"])

# Explicit import — pipeline.py and cve_tasks.py live outside app.workers.tasks/,
# so autodiscover won't find them. Importing registers the task decorators.
import app.workers.cve_tasks  # noqa: E402
import app.workers.pipeline  # noqa: E402, F401


@signals.worker_init.connect
def on_worker_init(**kwargs):
    logger.info(
        "Celery worker initialized — queues: default, analysis, export, security, email, webhooks, sync"
    )


@signals.worker_process_init.connect
def on_worker_process_init(**kwargs):
    """Initialize sync SQLAlchemy engine in each worker process."""
    from app.core.database import get_sync_engine

    get_sync_engine()
    logger.info("Worker process init — sync DB engine created")
