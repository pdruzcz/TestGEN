"""Integration tests for Story 3-13-domknięcie — SikuliX pipeline (AC1/AC3/AC5).

Exercises ``generate_sikulix_code`` end-to-end with mocked DB loaders + mocked
MinIO, but a REAL Pillow crop, so the assertions verify that real PNG pattern
bytes are produced, uploaded and recorded. Image-gated: skips when Pillow is
unavailable (parity with the 5 existing cropper tests).

The graceful-degradation path (no crop → script still generated) is covered by
a non-gated test that mocks ``crop_all_components``.
"""

import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.test_generation import sikulix_pipeline as sp


def _mock_db() -> AsyncMock:
    """Async DB session mock with a synchronous ``add`` (SQLAlchemy add is sync)."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _png_bytes(width: int = 200, height: int = 200) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _make_tc(tc_id: uuid.UUID, title: str, steps: list[dict]) -> SimpleNamespace:
    ns = SimpleNamespace(id=tc_id, title=title)
    ns.to_dict = lambda: {"id": str(tc_id), "title": title, "steps": steps}
    return ns


def _patch_pipeline(monkeypatch, *, test_cases, components, screenshot_bytes):
    """Patch DB loaders, MinIO and settings; capture uploads. Returns (uploads, download_calls)."""
    monkeypatch.setattr(sp, "_load_test_cases", AsyncMock(return_value=test_cases))
    monkeypatch.setattr(sp, "_load_gui_components", AsyncMock(return_value=components))
    monkeypatch.setattr(sp, "get_settings", lambda: SimpleNamespace(minio_bucket_name="test-bucket"))

    downloads: list[str] = []

    def _download(bucket, storage_key):
        downloads.append(storage_key)
        return screenshot_bytes

    monkeypatch.setattr(sp, "download_file_bytes", _download)

    uploads: list[tuple] = []

    def _upload(bucket, storage_key, data, length, content_type=None):
        uploads.append((storage_key, data.read(), content_type, length))

    monkeypatch.setattr(sp, "upload_file", _upload)
    return uploads, downloads


class TestSikulixPipelineRealPatterns:
    """AC1/AC3/AC5 — realne PNG patterny produkowane przez pipeline."""

    @pytest.fixture(autouse=True)
    def _require_pillow(self):
        pytest.importorskip("PIL", reason="Pillow wymagany dla realnych PNG patternow")

    async def test_produces_real_pngs_and_records_them(self, monkeypatch):
        tc_id = uuid.uuid4()
        comp_id = uuid.uuid4()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        tc = _make_tc(
            tc_id,
            "Login Flow",
            [{"action": "click", "component_id": str(comp_id)}],
        )
        components = [
            {
                "id": str(comp_id),
                "component_type": "button",
                "label": "Login",
                "bbox": {"x": 0, "y": 0, "w": 40, "h": 20},
                "confidence": 0.9,
                "storage_key": "tenant/proj/gui/shot.png",
            }
        ]
        uploads, downloads = _patch_pipeline(
            monkeypatch,
            test_cases=[tc],
            components=components,
            screenshot_bytes=_png_bytes(200, 200),
        )

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, project_id, [tc_id], tenant_id=tenant_id)

        assert len(records) == 1
        rec = records[0]
        assert rec.framework == "sikulix"
        assert rec.language == "python"
        assert rec.test_case_id == tc_id
        assert rec.tenant_id == tenant_id

        # AC1 — pattern_images odnotowane w TestCode
        assert rec.pattern_images is not None
        assert len(rec.pattern_images) == 1
        meta = rec.pattern_images[0]
        assert meta["name"] == "button_login.png"
        assert meta["component_id"] == str(comp_id)
        assert meta["storage_key"].endswith("images/button_login.png")
        assert f"{tenant_id}/{project_id}/sikuli/{tc_id}/images" in meta["storage_key"]

        # AC3 — skrypt referuje realny pattern (nazwa zgodna z wyprodukowanym PNG)
        assert 'Pattern("images/button_login.png")' in rec.code

        # AC1 — screenshot pobrany raz, PNG wgrany raz z realnymi bajtami
        assert downloads == ["tenant/proj/gui/shot.png"]
        assert len(uploads) == 1
        key, png_bytes, content_type, length = uploads[0]
        assert content_type == "image/png"
        assert key.endswith("images/button_login.png")
        assert length == len(png_bytes)
        # realny, otwieralny PNG
        from PIL import Image

        Image.open(io.BytesIO(png_bytes)).verify()

        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    async def test_groups_components_by_screenshot(self, monkeypatch):
        """Dwa komponenty na tym samym screencie → 1 download, 2 uploady."""
        tc_id = uuid.uuid4()
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()

        tc = _make_tc(
            tc_id,
            "Form",
            [
                {"action": "click", "component_id": str(comp_a)},
                {"action": "type", "component_id": str(comp_b), "value": "x"},
            ],
        )
        components = [
            {
                "id": str(comp_a),
                "component_type": "button",
                "label": "Login",
                "bbox": {"x": 0, "y": 0, "w": 40, "h": 20},
                "confidence": 0.9,
                "storage_key": "tenant/proj/gui/shot.png",
            },
            {
                "id": str(comp_b),
                "component_type": "input",
                "label": "User",
                "bbox": {"x": 50, "y": 0, "w": 40, "h": 20},
                "confidence": 0.9,
                "storage_key": "tenant/proj/gui/shot.png",
            },
        ]
        uploads, downloads = _patch_pipeline(
            monkeypatch,
            test_cases=[tc],
            components=components,
            screenshot_bytes=_png_bytes(200, 200),
        )

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, uuid.uuid4(), [tc_id], tenant_id=uuid.uuid4())

        rec = records[0]
        names = sorted(m["name"] for m in rec.pattern_images)
        assert names == ["button_login.png", "input_user.png"]
        assert len(downloads) == 1  # ten sam screenshot pobrany raz
        assert len(uploads) == 2

    async def test_label_match_linkage_crops_pattern(self, monkeypatch):
        """AC2 — linkage przez label-match (target) też produkuje pattern."""
        tc_id = uuid.uuid4()
        tc = _make_tc(tc_id, "Login", [{"action": "click", "target": "Login Submit"}])
        components = [
            {
                "id": str(uuid.uuid4()),
                "component_type": "button",
                "label": "Login Submit",
                "bbox": {"x": 0, "y": 0, "w": 30, "h": 20},
                "confidence": 0.8,
                "storage_key": "tenant/proj/gui/shot.png",
            }
        ]
        uploads, _ = _patch_pipeline(
            monkeypatch,
            test_cases=[tc],
            components=components,
            screenshot_bytes=_png_bytes(100, 100),
        )

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, uuid.uuid4(), [tc_id], tenant_id=uuid.uuid4())

        rec = records[0]
        assert [m["name"] for m in rec.pattern_images] == ["button_login_submit.png"]
        assert 'Pattern("images/button_login_submit.png")' in rec.code
        assert len(uploads) == 1

    async def test_inline_component_without_screenshot_is_script_only(self, monkeypatch):
        """Inline ``step.component`` z bbox (bez storage_key) → skrypt referuje pattern, ale PNG nie powstaje."""
        tc_id = uuid.uuid4()
        tc = _make_tc(
            tc_id,
            "Inline",
            [
                {
                    "action": "click",
                    "component": {
                        "component_type": "button",
                        "label": "OK",
                        "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
                    },
                }
            ],
        )
        uploads, downloads = _patch_pipeline(
            monkeypatch,
            test_cases=[tc],
            components=[],
            screenshot_bytes=_png_bytes(100, 100),
        )

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, uuid.uuid4(), [tc_id], tenant_id=uuid.uuid4())

        rec = records[0]
        assert 'Pattern("images/button_ok.png")' in rec.code
        assert rec.pattern_images is None  # nic nie wycięto (brak źródła screenshotu)
        assert uploads == []
        assert downloads == []


class TestSikulixPipelineGracefulDegrade:
    """Task 2.3 — bez cropu (brak Pillow / puste) skrypt i tak powstaje."""

    async def test_empty_crops_still_emits_script(self, monkeypatch):
        tc_id = uuid.uuid4()
        comp_id = uuid.uuid4()
        tc = _make_tc(tc_id, "Login", [{"action": "click", "component_id": str(comp_id)}])
        components = [
            {
                "id": str(comp_id),
                "component_type": "button",
                "label": "Login",
                "bbox": {"x": 0, "y": 0, "w": 40, "h": 20},
                "confidence": 0.9,
                "storage_key": "tenant/proj/gui/shot.png",
            }
        ]
        uploads, _ = _patch_pipeline(
            monkeypatch,
            test_cases=[tc],
            components=components,
            screenshot_bytes=_png_bytes(200, 200),
        )
        # Symulacja braku Pillow: crop nic nie zwraca (jak `crop_all_components` degrade).
        monkeypatch.setattr(sp, "crop_all_components", lambda data, comps: [])

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, uuid.uuid4(), [tc_id], tenant_id=uuid.uuid4())

        assert len(records) == 1
        rec = records[0]
        # skrypt nadal wygenerowany i referuje pattern (nazwa z metadanych komponentu)
        assert 'Pattern("images/button_login.png")' in rec.code
        assert "from sikuli import *" in rec.code
        # ale żadne PNG nie zostały wyprodukowane/zapisane
        assert rec.pattern_images is None
        assert uploads == []

    async def test_no_test_cases_returns_empty(self, monkeypatch):
        monkeypatch.setattr(sp, "_load_test_cases", AsyncMock(return_value=[]))
        monkeypatch.setattr(sp, "_load_gui_components", AsyncMock(return_value=[]))
        monkeypatch.setattr(sp, "get_settings", lambda: SimpleNamespace(minio_bucket_name="b"))

        db = _mock_db()
        records = await sp.generate_sikulix_code(db, uuid.uuid4(), [uuid.uuid4()], tenant_id=uuid.uuid4())
        assert records == []
