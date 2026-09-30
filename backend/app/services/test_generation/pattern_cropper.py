"""Pattern cropper — Epic 3, Story 3.13 (AC2).

Wycina regiony elementow GUI (bounding box) z oryginalnych screenshotow
i zapisuje je jako patterny PNG dla generatora SikuliX.
"""

import io
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CroppedPattern:
    """Wycinek elementu UI gotowy do zapisania jako pattern SikuliX."""

    name: str
    image_bytes: bytes
    component_id: str | None = None
    similarity: float | None = None


def _sanitize(value: Any) -> str:
    """Sanityzuj fragment nazwy pliku patternu."""
    text = str(value).lower()
    text = re.sub(r"[\s-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "element"


def _extract_bbox(bbox: dict[str, Any]) -> tuple[int, int, int, int]:
    """Wyciagnij (x, y, w, h) z roznych formatow bbox."""
    x = int(bbox.get("x", 0))
    y = int(bbox.get("y", 0))
    if "w" in bbox or "h" in bbox:
        w = int(bbox.get("w", 0))
        h = int(bbox.get("h", 0))
    else:
        # format x1/y1/x2/y2
        x2 = int(bbox.get("x2", x))
        y2 = int(bbox.get("y2", y))
        w = max(0, x2 - x)
        h = max(0, y2 - y)
    return x, y, w, h


def crop_element(screenshot_bytes: bytes, bbox: dict[str, Any]) -> bytes:
    """Przytnij region elementu (bbox) z obrazu screenshotu (AC2).

    Args:
        screenshot_bytes: surowe bajty oryginalnego screenshotu
        bbox: slownik z (x, y, w, h) lub (x, y, x2, y2)

    Returns:
        Bajty PNG wycietego regionu.

    Raises:
        ValueError: gdy bbox jest pusty lub poza obrazem.
        RuntimeError: gdy biblioteka Pillow nie jest dostepna.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Brak biblioteki Pillow — wycinanie patternow SikuliX niedostepne."
        ) from exc

    x, y, w, h = _extract_bbox(bbox)
    if w <= 0 or h <= 0:
        raise ValueError(f"Nieprawidlowy bbox (w/h <= 0): {bbox}")

    image = Image.open(io.BytesIO(screenshot_bytes))
    img_w, img_h = image.size

    # Przytnij region do granic obrazu (clamp), aby uniknac pustego wycinka.
    left = max(0, min(x, img_w))
    top = max(0, min(y, img_h))
    right = max(left, min(x + w, img_w))
    bottom = max(top, min(y + h, img_h))
    if right <= left or bottom <= top:
        raise ValueError(f"Bbox poza obrazem {image.size}: {bbox}")

    cropped = image.crop((left, top, right, bottom))
    out = io.BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()


def crop_all_components(
    screenshot_bytes: bytes,
    components: list[dict[str, Any]],
) -> list[CroppedPattern]:
    """Wytnij patterny dla wszystkich komponentow ze screenshotu (AC2).

    Args:
        screenshot_bytes: bajty oryginalnego screenshotu
        components: lista komponentow z polami bbox, component_type, label

    Returns:
        Lista CroppedPattern (pomija komponenty bez poprawnego bbox).
    """
    patterns: list[CroppedPattern] = []
    for comp in components:
        bbox = comp.get("bbox") or comp.get("bounding_box")
        if not isinstance(bbox, dict):
            continue
        ctype = comp.get("component_type") or comp.get("type") or "element"
        label = comp.get("label") or comp.get("text") or "element"
        name = f"{_sanitize(ctype)}_{_sanitize(label)}.png"
        try:
            image_bytes = crop_element(screenshot_bytes, bbox)
        except RuntimeError as exc:
            # Brak Pillow — przerwij caly crop (degradacja jak w GUI orchestratorze).
            logger.warning("Crop patternow pominiety: %s", exc)
            return []
        except (ValueError, OSError) as exc:
            logger.warning("Pominieto crop komponentu %s: %s", name, exc)
            continue
        patterns.append(
            CroppedPattern(
                name=name,
                image_bytes=image_bytes,
                component_id=str(comp.get("id")) if comp.get("id") else None,
            )
        )
    return patterns
