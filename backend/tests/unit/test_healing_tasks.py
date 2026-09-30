"""Unit tests for the healing Celery task — Story 1.51."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.healing_report import HealingReport, HealingStatus
from app.workers.tasks.healing_tasks import _run_healing_impl


def _mock_session_ctx(mock_session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _result(rows):
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    r.scalars.return_value.one_or_none.return_value = rows[0] if rows else None
    return r


def _comp(label=None, **attrs):
    return SimpleNamespace(
        id=uuid.uuid4(),
        component_type="button",
        label=label,
        attributes=attrs,
        bbox=None,
    )


class TestRunHealingImpl:
    @patch("app.services.analysis.llm_gateway.get_llm_gateway")
    @patch("app.core.database.task_session")
    async def test_fills_pending_report_and_commits(self, mock_ses_factory, mock_get_gateway):
        mock_get_gateway.return_value = None  # native-only
        session = AsyncMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)

        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        report = HealingReport(
            id=uuid.uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            version_a=str(uuid.uuid4()),
            version_b=str(uuid.uuid4()),
            status=HealingStatus.PENDING,
        )

        code = 'driver.find_element(By.ID, "login-btn")'
        tcode = SimpleNamespace(id=uuid.uuid4(), code=code, framework="selenium", test_case_id=uuid.uuid4())

        # execute order: SET LOCAL, select(report), gui_a, gui_b, test_codes
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                _result([report]),
                _result([_comp(label="Login", **{"id": "login-btn"})]),
                _result([_comp(label="Login", **{"data-testid": "login-submit"})]),
                _result([tcode]),
            ]
        )

        out = await _run_healing_impl(str(report.id), str(tenant_id))

        assert out["status"] == "healed"
        assert out["report_id"] == str(report.id)
        assert out["stats"]["healed"] == 1
        assert report.status == HealingStatus.HEALED
        assert session.commit.await_count == 1

    @patch("app.services.analysis.llm_gateway.get_llm_gateway")
    @patch("app.core.database.task_session")
    async def test_missing_report_returns_failed(self, mock_ses_factory, mock_get_gateway):
        mock_get_gateway.return_value = None
        session = AsyncMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)

        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                _result([]),  # report not found
            ]
        )

        out = await _run_healing_impl(str(uuid.uuid4()), str(uuid.uuid4()))
        assert out["status"] == "failed"
        assert out["error"] == "not_found"
        session.commit.assert_not_awaited()
