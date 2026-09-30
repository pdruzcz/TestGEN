"""Testy zadania Celery check_thresholds — Story 7.11, Task 3 (AC6).

Hourly sprawdzanie progów zużycia per tenant → NotificationService.
Wzorzec mockowania: test_usage_snapshot_task.
"""

from unittest.mock import AsyncMock, MagicMock, patch


def _mock_session_ctx(mock_session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestCheckThresholdsImpl:
    @patch("app.core.database.task_session")
    async def test_deleguje_do_notification_service_i_commituje(self, mock_ses_factory):
        session = AsyncMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)
        session.execute = AsyncMock(return_value=MagicMock())  # SET LOCAL RLS

        stats = {"tenants": 5, "created": 7}
        with patch(
            "app.services.notification_service.NotificationService.check_and_notify_thresholds",
            AsyncMock(return_value=stats),
        ) as run:
            from app.workers.tasks.check_thresholds import _check_thresholds_impl

            result = await _check_thresholds_impl()

        assert result == stats
        run.assert_awaited_once()
        session.commit.assert_awaited_once()
        # Kontekst RLS admina (NIL UUID) — przepływ systemowy bez JWT.
        assert "SET LOCAL app.current_tenant" in session.execute.await_args_list[0].args[0].text


class TestBeatSchedule:
    def test_zadanie_w_harmonogramie_co_godzine(self):
        from celery.schedules import crontab

        from app.workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule.get("billing-check-thresholds-hourly")
        assert entry is not None
        assert entry["task"] == "app.workers.tasks.check_thresholds.check_usage_thresholds"
        assert entry["schedule"] == crontab(minute=0)  # co godzinę o pełnej
