"""GUI user-flow reconstruction from screenshot sequences — Story 3.9.

Given an ordered sequence of analysed screenshots, reconstruct the likely user
flow by matching components across consecutive screens (IoU + label + type),
optionally computing a pixel diff, and inferring the user action that connects
each pair of screens.

The component matching and action inference is pure Python so it is unit-testable
without heavy dependencies. ``scipy`` (Hungarian assignment) and
``scikit-image`` / ``numpy`` (pixel diff) are optional: when missing the code
falls back to a greedy matcher and skips the pixel-diff signal, degrading
gracefully (AC consistent with Story 3.8 NFR-REL-003).
"""

import logging
from dataclasses import dataclass, field

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.models import DetectedComponent

logger = logging.getLogger(__name__)

# Weighted scoring for a candidate component match.
_W_IOU = 0.4
_W_LABEL = 0.3
_W_TYPE = 0.3
_MATCH_THRESHOLD = 0.6

# Pixel-diff ratio above which a transition is treated as full-screen navigation.
_NAVIGATION_DIFF_RATIO = 0.5

# Action types (AC-3).
ACTION_BUTTON_CLICK = "button_click"
ACTION_INPUT_FILL = "input_fill"
ACTION_NAVIGATION = "navigation"
ACTION_CHECKBOX_TOGGLE = "checkbox_toggle"
ACTION_DROPDOWN_SELECT = "dropdown_select"
ACTION_UNKNOWN = "unknown"

# Higher number = higher priority when several signals fire on one transition.
_ACTION_PRIORITY = {
    ACTION_NAVIGATION: 5,
    ACTION_BUTTON_CLICK: 4,
    ACTION_DROPDOWN_SELECT: 3,
    ACTION_CHECKBOX_TOGGLE: 2,
    ACTION_INPUT_FILL: 1,
    ACTION_UNKNOWN: 0,
}


@dataclass
class ScreenAnalysis:
    """In-memory view of one analysed screenshot fed to the reconstructor."""

    screenshot_id: str
    sequence: int
    components: list[DetectedComponent] = field(default_factory=list)
    image: object | None = None  # decoded numpy array, optional (for pixel diff)


@dataclass
class ComponentMatch:
    index_a: int
    index_b: int
    confidence: float


@dataclass
class UserAction:
    action_type: str
    target_element: str | None
    confidence: float
    description: str


def _levenshtein(a: str, b: str) -> int:
    """Classic dynamic-programming edit distance (pure Python)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _label_similarity(a: str | None, b: str | None) -> float:
    """Normalised label similarity in ``[0, 1]`` (1 = identical)."""
    la = (a or "").strip().lower()
    lb = (b or "").strip().lower()
    if not la and not lb:
        return 0.0
    if not la or not lb:
        return 0.0
    dist = _levenshtein(la, lb)
    longest = max(len(la), len(lb))
    return 1.0 - dist / longest if longest else 0.0


def _match_score(ca: DetectedComponent, cb: DetectedComponent) -> float:
    iou = ca.bbox.iou(cb.bbox)
    label = _label_similarity(ca.label, cb.label)
    type_match = 1.0 if ca.component_type == cb.component_type else 0.0
    return _W_IOU * iou + _W_LABEL * label + _W_TYPE * type_match


def match_components(
    comps_a: list[DetectedComponent], comps_b: list[DetectedComponent]
) -> list[ComponentMatch]:
    """Match components from screen A to screen B.

    Uses the Hungarian algorithm (``scipy``) for an optimal assignment when
    available, otherwise a greedy best-first fallback. Only matches scoring above
    :data:`_MATCH_THRESHOLD` are returned.
    """
    if not comps_a or not comps_b:
        return []

    scores = [[_match_score(ca, cb) for cb in comps_b] for ca in comps_a]

    pairs: list[tuple[int, int]] = []
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment

        cost = -np.array(scores)
        rows, cols = linear_sum_assignment(cost)
        pairs = list(zip(rows.tolist(), cols.tolist(), strict=True))
    except ImportError:
        used_b: set[int] = set()
        flat = sorted(
            (
                (scores[i][j], i, j)
                for i in range(len(comps_a))
                for j in range(len(comps_b))
            ),
            reverse=True,
        )
        used_a: set[int] = set()
        for _score, i, j in flat:
            if i in used_a or j in used_b:
                continue
            used_a.add(i)
            used_b.add(j)
            pairs.append((i, j))

    matches: list[ComponentMatch] = []
    for i, j in pairs:
        conf = scores[i][j]
        if conf >= _MATCH_THRESHOLD:
            matches.append(ComponentMatch(index_a=i, index_b=j, confidence=conf))
    return matches


def compute_pixel_diff(image_a, image_b) -> tuple[float | None, str | None]:
    """Return ``(diff_ratio, warning)``.

    ``diff_ratio`` is the fraction of pixels that differ beyond a tolerance, or
    ``None`` when the optional imaging stack is unavailable.
    """
    if image_a is None or image_b is None:
        return None, None
    try:
        import numpy as np
    except ImportError:
        return None, "Brak numpy — pominięto pixel diff między ekranami."

    try:
        a = np.asarray(image_a)
        b = np.asarray(image_b)
        if a.shape != b.shape:
            return None, "Różne wymiary ekranów — pominięto pixel diff."
        delta = np.abs(a.astype("int16") - b.astype("int16"))
        if delta.ndim == 3:
            delta = delta.max(axis=2)
        changed = (delta > 30).sum()
        total = delta.size if delta.size else 1
        return float(changed) / float(total), None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Pixel diff failed: %s", exc)
        return None, f"Pixel diff nie powiódł się: {exc}"


def detect_actions(
    comps_a: list[DetectedComponent],
    comps_b: list[DetectedComponent],
    matches: list[ComponentMatch],
    pixel_diff_ratio: float | None = None,
) -> list[UserAction]:
    """Infer candidate user actions for an A -> B transition (AC-3)."""
    actions: list[UserAction] = []
    matched_a = {m.index_a for m in matches}

    # Full-screen change -> navigation.
    if pixel_diff_ratio is not None and pixel_diff_ratio >= _NAVIGATION_DIFF_RATIO:
        actions.append(
            UserAction(
                ACTION_NAVIGATION,
                target_element=None,
                confidence=min(1.0, pixel_diff_ratio),
                description="Nawigacja do nowego ekranu (duża zmiana układu).",
            )
        )
    elif pixel_diff_ratio is None:
        # Heuristic navigation: very little component overlap between screens.
        overlap = len(matches) / max(len(comps_a), len(comps_b), 1)
        if comps_a and comps_b and overlap < 0.25:
            actions.append(
                UserAction(
                    ACTION_NAVIGATION,
                    target_element=None,
                    confidence=0.6,
                    description="Prawdopodobna nawigacja (niewielkie pokrycie komponentów).",
                )
            )

    # Components that disappeared on B -> likely interacted with.
    for i, ca in enumerate(comps_a):
        if i in matched_a:
            continue
        if ca.component_type == GUIComponentType.BUTTON:
            actions.append(
                UserAction(
                    ACTION_BUTTON_CLICK,
                    target_element=ca.label,
                    confidence=0.7,
                    description=f"Kliknięcie przycisku „{ca.label or 'przycisk'}”.",
                )
            )
        elif ca.component_type == GUIComponentType.CHECKBOX:
            actions.append(
                UserAction(
                    ACTION_CHECKBOX_TOGGLE,
                    target_element=ca.label,
                    confidence=0.6,
                    description=f"Zmiana stanu pola wyboru „{ca.label or 'checkbox'}”.",
                )
            )
        elif ca.component_type == GUIComponentType.DROPDOWN:
            actions.append(
                UserAction(
                    ACTION_DROPDOWN_SELECT,
                    target_element=ca.label,
                    confidence=0.6,
                    description=f"Wybór z listy rozwijanej „{ca.label or 'dropdown'}”.",
                )
            )

    # Matched inputs whose label/text changed -> filled.
    for m in matches:
        ca = comps_a[m.index_a]
        cb = comps_b[m.index_b]
        if ca.component_type == GUIComponentType.INPUT and (ca.label or "") != (cb.label or ""):
            actions.append(
                UserAction(
                    ACTION_INPUT_FILL,
                    target_element=cb.label or ca.label,
                    confidence=0.65,
                    description=f"Wypełnienie pola „{cb.label or ca.label or 'input'}”.",
                )
            )

    return actions


def best_action(actions: list[UserAction]) -> UserAction:
    """Pick the highest-priority, then highest-confidence action for a transition."""
    if not actions:
        return UserAction(
            ACTION_UNKNOWN,
            target_element=None,
            confidence=0.0,
            description="Nie rozpoznano akcji między ekranami.",
        )
    return max(
        actions,
        key=lambda a: (_ACTION_PRIORITY.get(a.action_type, 0), a.confidence),
    )


@dataclass
class FlowStepResult:
    sequence: int
    action: str
    action_type: str
    target_element: str | None
    confidence: float
    source_screenshot_id: str
    next_screenshot_id: str


@dataclass
class FlowReconstructionResult:
    name: str
    source_screenshot_ids: list[str]
    steps: list[FlowStepResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _describe_screen(screen: ScreenAnalysis) -> str:
    """Compact textual description of a screen's components for the LLM prompt."""
    parts = []
    for c in screen.components:
        label = c.label or "—"
        parts.append(f"{c.component_type.value}:{label}")
    return f"Ekran {screen.sequence} ({screen.screenshot_id}): " + ", ".join(parts or ["brak komponentów"])


async def enrich_with_llm(
    result: FlowReconstructionResult,
    screens: list[ScreenAnalysis],
    llm_gateway,
    tenant_id=None,
) -> FlowReconstructionResult:
    """Enrich native step descriptions with LLM natural-language narration (AC-6).

    The configured gateway is text-only, so screens are described textually
    (component type + OCR label) rather than sent as raw images. Failures leave
    the native result untouched and append a warning (graceful degradation).
    """
    from app.services.analysis.gui.llm_prompt import build_flow_prompt, parse_flow_response
    from app.services.analysis.llm_gateway import LLMMessage

    if not result.steps:
        return result

    ordered = sorted(screens, key=lambda s: s.sequence)
    screen_descriptions = [_describe_screen(s) for s in ordered]
    prompt = build_flow_prompt(screen_descriptions, result.steps)

    try:
        response = await llm_gateway.complete(
            provider="anthropic",
            messages=[LLMMessage(role="user", content=prompt)],
            module="gui_flow",
            task_type="flow_reconstruction",
            tenant_id=tenant_id,
        )
        enriched = parse_flow_response(response.content)
    except Exception as exc:  # pragma: no cover - network/parse failure
        logger.warning("LLM flow enrichment failed: %s", exc)
        result.warnings.append("Wzbogacenie LLM nie powiodło się — użyto wyniku natywnego.")
        return result

    for step in result.steps:
        text = enriched.get(step.sequence)
        if text:
            step.action = text
    return result


class GUIFlowReconstructor:
    """Reconstruct a user flow from an ordered list of analysed screenshots."""

    def reconstruct(self, screens: list[ScreenAnalysis], name: str | None = None) -> FlowReconstructionResult:
        """Build a flow by analysing each consecutive pair of screens (AC-1..4)."""
        warnings: list[str] = []
        ordered = sorted(screens, key=lambda s: s.sequence)

        if len(ordered) < 2:
            warnings.append("Potrzebne są co najmniej dwa ekrany do rekonstrukcji przepływu.")
            return FlowReconstructionResult(
                name=name or "Przepływ GUI",
                source_screenshot_ids=[s.screenshot_id for s in ordered],
                steps=[],
                warnings=warnings,
            )

        steps: list[FlowStepResult] = []
        for idx in range(len(ordered) - 1):
            a = ordered[idx]
            b = ordered[idx + 1]
            matches = match_components(a.components, b.components)
            diff_ratio, diff_warning = compute_pixel_diff(a.image, b.image)
            if diff_warning:
                warnings.append(diff_warning)
            actions = detect_actions(a.components, b.components, matches, diff_ratio)
            action = best_action(actions)
            steps.append(
                FlowStepResult(
                    sequence=idx + 1,
                    action=action.description,
                    action_type=action.action_type,
                    target_element=action.target_element,
                    confidence=action.confidence,
                    source_screenshot_id=a.screenshot_id,
                    next_screenshot_id=b.screenshot_id,
                )
            )

        return FlowReconstructionResult(
            name=name or "Przepływ GUI",
            source_screenshot_ids=[s.screenshot_id for s in ordered],
            steps=steps,
            warnings=warnings,
        )
