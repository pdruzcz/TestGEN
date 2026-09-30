"""Celery tasks for sending emails."""

import logging

import httpx

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Retryable exceptions — HTTP/network transient errors only
_RETRYABLE = (httpx.HTTPStatusError, ConnectionError, OSError)

_RETRY_DELAYS = (60, 300, 600)


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="email",
)
def send_verification_email_task(self, user_email: str, token: str, name: str) -> None:
    from app.services.email.email_service import send_verification_email

    try:
        send_verification_email(user_email, token, name)
    except _RETRYABLE as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for verification email to %s (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            user_email,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="email",
)
def send_password_reset_email_task(self, user_email: str, token: str, name: str) -> None:
    from app.services.email.email_service import send_password_reset_email

    try:
        send_password_reset_email(user_email, token, name)
    except _RETRYABLE as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for password reset email to %s (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            user_email,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="email",
)
def send_invitation_email_task(self, user_email: str, token: str, inviter_name: str, company_name: str) -> None:
    from app.services.email.email_service import send_invitation_email

    try:
        send_invitation_email(user_email, token, inviter_name, company_name)
    except _RETRYABLE as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for invitation email to %s (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            user_email,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="email",
)
def send_sync_degraded_email_task(
    self, user_email: str, provider: str, project_name: str, error: str
) -> None:
    """Powiadomienie o zdegradowanej synchronizacji z TMS (Story 8.11, AC6)."""
    from app.services.email.email_service import send_sync_degraded_email

    try:
        send_sync_degraded_email(user_email, provider, project_name, error)
    except _RETRYABLE as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for sync-degraded email to %s (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            user_email,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
