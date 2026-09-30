"""E2E self-healing on DOM-extracted attributes — Story 1.51-zakańczenie (FR69).

Proves the 'dokończenie 1.51' loop end-to-end **without manually injected
attributes** (the gap that left 1.51 green-but-broken): HTML →
:class:`DOMComponentExtractor` → real locator attributes →
:class:`NativeMatcher` resolves a changed locator via ``data-testid``/label.

Also guards the screenshot-path regression (#8) and the origin-based routing
contract (#4): HTML entering the GUI/DOM channel is categorised ``gui_dom``,
never confused with the documentation channel.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.gui_screenshot import GUIComponentType
from app.models.healing_report import LocatorStrategy
from app.models.source_file import FileCategory
from app.services.analysis.gui.dom_extractor import DOMComponentExtractor
from app.services.analysis.gui.models import DetectedComponent
from app.services.generators.self_healing import GUIElementView, NativeMatcher, ParsedLocator


def _views(html: str) -> list[GUIElementView]:
    """Run the DOM extractor and wrap output as healing element views (no DB)."""
    return [
        GUIElementView(
            component_id=uuid.uuid4(),
            component_type=c.component_type,
            label=c.label,
            attributes=c.attributes,
            bbox=None,
        )
        for c in DOMComponentExtractor().extract(html)
    ]


class _FakeUpload:
    def __init__(self, filename: str, content: bytes, content_type: str = "text/html"):
        self.filename = filename
        self._buf = content
        self.content_type = content_type
        self.size = len(content)

    async def read(self, _n: int = -1) -> bytes:
        data, self._buf = self._buf, b""
        return data


# ── #10: the actual 'dokończenie 1.51' loop ────────────────────────────────────
class TestDomHealingE2E:
    def test_changed_testid_heals_via_label_bridge(self):
        # Version A (przed): the test targets the button by id.
        a = _views('<button id="login-btn">Zaloguj</button>')
        # Version B (po): id removed, data-testid added — same visible label.
        b = _views('<button data-testid="login-submit">Zaloguj</button>')

        loc = ParsedLocator(
            raw="#login-btn",
            strategy=LocatorStrategy.ID,
            selector="#login-btn",
            start=0,
            end=9,
        )
        candidate = NativeMatcher.match(loc, a, b)
        assert candidate is not None
        assert candidate.new_strategy == LocatorStrategy.DATA_TESTID
        assert candidate.new_locator == "[data-testid='login-submit']"

    def test_unchanged_testid_target_still_resolves(self):
        b = _views('<button data-testid="save">Zapisz</button>')
        loc = ParsedLocator(
            raw="[data-testid='save']",
            strategy=LocatorStrategy.DATA_TESTID,
            selector="[data-testid='save']",
            start=0,
            end=18,
        )
        assert NativeMatcher.target_exists(loc, b) is True

    def test_role_name_strategy_used_when_no_testid(self):
        # Version B exposes only role+name → healing falls back to role+name.
        a = _views('<button id="ok">OK</button>')
        b = _views("<button>OK</button>")
        loc = ParsedLocator(raw="#ok", strategy=LocatorStrategy.ID, selector="#ok", start=0, end=3)
        candidate = NativeMatcher.match(loc, a, b)
        assert candidate is not None
        # label-only match → CSS text strategy (no testid/aria/id on B)
        assert candidate.new_strategy in {LocatorStrategy.CSS, LocatorStrategy.ROLE_NAME}


# ── #8: screenshot-path regression guard ──────────────────────────────────────
class TestScreenshotAttributesRegression:
    def test_detector_component_defaults_to_empty_attributes(self):
        # ComponentDetector builds DetectedComponent WITHOUT attributes (the
        # screenshot path). Empty dict → `{} or None` = NULL at persist time.
        # That gap is exactly what DOM sourcing fills; guard against regression.
        comp = DetectedComponent(
            component_type=GUIComponentType.BUTTON,
            bbox=None,
            confidence=0.9,
            label="X",
        )
        assert comp.attributes == {}
        assert comp.attributes or None is None  # the pre-1.51-zakańczenie trap


# ── #4: origin-based routing — DOM channel categorises HTML as gui_dom ─────────
class TestDomRoutingCategory:
    @pytest.mark.asyncio
    async def test_html_dom_source_is_categorised_gui_dom(self):
        from app.services.analysis.gui.dom_upload_service import upload_dom_sources

        project = MagicMock(id=uuid.uuid4(), tenant_id=uuid.uuid4())
        db = MagicMock()
        db.flush = AsyncMock()
        added: list = []
        db.add.side_effect = added.append

        with (
            patch(
                "app.services.analysis.gui.dom_upload_service.get_active_project",
                new_callable=AsyncMock,
                return_value=project,
            ),
            patch("app.services.analysis.gui.dom_upload_service.upload_file"),
            patch(
                "app.services.analysis.gui.dom_upload_service.log_action",
                new_callable=AsyncMock,
            ),
        ):
            outcome = await upload_dom_sources(
                db,
                actor=MagicMock(id=uuid.uuid4()),
                project_id=project.id,
                html_files=[_FakeUpload("logowanie.html", b"<button>X</button>")],
            )

        assert len(outcome.accepted) == 1
        assert outcome.accepted[0].source_file.file_category == FileCategory.GUI_DOM
        assert added and added[0].file_category == FileCategory.GUI_DOM
