"""Unit tests for the dead-code pass in code_error_tasks — Story 5.10.

Exercises `_run_code_error_detection_impl` with a scripted session and
patched MinIO download: project-wide detection, fingerprint/status
persistence, and AC4 dismissal dedupe (dismissed findings must not come
back when the same code state is re-scanned).
"""

import contextlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.tasks.code_error_tasks import _DEFAULT_CATEGORIES

SAMPLE_APP = """def _unused_helper():
    return 1


def process_order(x):
    return validate(x)


def validate(x):
    return x


z = process_order(1)
"""


def _fake_source_file(fid, path, content):
    return SimpleNamespace(
        id=fid,
        project_id=None,
        detected_language="python",
        file_size=len(content),
        storage_key=f"projects/x/{path}",
        original_path=path,
        filename=path.split("/")[-1],
        is_cleaned_up=False,
    )


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


def _script_session(source_rows, dismissed_rows=(), capture=None):
    """Build a mock AsyncSession matching the impl's execute sequence:
    SET LOCAL → select SourceFiles → select dismissed → DELETE."""
    session = MagicMock()
    session.add = MagicMock(side_effect=lambda e: capture.append(e) if capture is not None else None)
    session.commit = AsyncMock()

    session.execute = AsyncMock(
        side_effect=[
            _FakeResult([]),  # SET LOCAL app.current_tenant
            _FakeResult(source_rows),  # select(SourceFile)
            _FakeResult(list(dismissed_rows)),  # select dismissed fingerprints
            _FakeResult([]),  # DELETE
        ]
    )

    @contextlib.asynccontextmanager
    async def fake_session():
        yield session

    return session, fake_session


async def _run(source_rows, dismissed_rows=(), capture=None):
    from app.workers.tasks.code_error_tasks import _run_code_error_detection_impl

    _session, fake_session = _script_session(source_rows, dismissed_rows, capture)
    with (
        patch("app.core.database.task_session", return_value=fake_session()),
        patch("app.core.storage.download_file_bytes", side_effect=lambda bucket, key: SAMPLE_APP.encode()),
    ):
        return await _run_code_error_detection_impl(str(uuid.uuid4()), str(uuid.uuid4()), ["dead_code"])


@pytest.mark.asyncio
class TestDeadCodeScanPass:
    async def test_dead_code_finding_persisted_with_fingerprint_and_status(self):
        pid = uuid.uuid4()
        sf = _fake_source_file(pid, "app.py", SAMPLE_APP)
        captured: list = []

        result = await _run([sf], capture=captured)

        dead = [e for e in captured if e.category.value == "dead_code"]
        assert len(dead) == 1
        err = dead[0]
        assert err.message.startswith("Funkcja '_unused_helper'")
        assert err.status == "open"
        assert err.fingerprint == f"app.py:_unused_helper:{err.fingerprint.split(':')[-1]}"
        assert len(err.fingerprint.split(":")[-1]) == 8
        assert result["status"] == "completed"

    async def test_dismissed_fingerprint_not_reinserted(self):
        """AC4: a finding dismissed as false_positive must not come back on
        a re-scan of the same code state."""
        pid = uuid.uuid4()
        sf = _fake_source_file(pid, "app.py", SAMPLE_APP)

        from app.services.gap_analysis.error_detectors.dead_code_detector import (
            build_fingerprint,
        )

        source_slice = "\n".join(SAMPLE_APP.splitlines()[0:2])
        dismissed_fp = build_fingerprint("app.py", "_unused_helper", source_slice)

        captured: list = []
        result = await _run([sf], dismissed_rows=[dismissed_fp], capture=captured)

        dead = [e for e in captured if e.category.value == "dead_code"]
        assert dead == []
        assert result["total_errors"] == 0

    async def test_delete_keeps_false_positive_rows(self):
        """AC4: the rescan DELETE must preserve false_positive rows."""
        pid = uuid.uuid4()
        sf = _fake_source_file(pid, "app.py", SAMPLE_APP)

        session, fake_session = _script_session([sf], [])
        with (
            patch("app.core.database.task_session", return_value=fake_session()),
            patch("app.core.storage.download_file_bytes", side_effect=lambda b, k: SAMPLE_APP.encode()),
        ):
            from app.workers.tasks.code_error_tasks import _run_code_error_detection_impl

            await _run_code_error_detection_impl(str(uuid.uuid4()), str(uuid.uuid4()), ["dead_code"])

        delete_sqls = [
            c.args[0].text
            for c in session.execute.await_args_list
            if c.args and "DELETE FROM code_errors" in getattr(c.args[0], "text", "")
        ]
        assert len(delete_sqls) == 1
        assert "status != 'false_positive'" in delete_sqls[0]


class TestDefaultCategories:
    def test_dead_code_in_defaults(self):
        assert "dead_code" in _DEFAULT_CATEGORIES
        assert _DEFAULT_CATEGORIES.count("dead_code") == 1
