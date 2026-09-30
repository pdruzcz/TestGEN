"""Visual-regression test-code generation — Epic 3, Story 3.10 (AC-6).

Renders Playwright / Cypress visual-regression test code from a classified
:class:`VisualComparisonResult`. Templates live in ``templates/`` and are loaded
via Jinja2 (``jinja2`` is available in this environment).

Each classified change produces one test case (description + screenshot
assertion). When no changes are detected a single baseline-guard test is
emitted so the generated suite is never empty.
"""

import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.analysis.gui.visual_regression import VisualComparisonResult

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

PLAYWRIGHT = "playwright"
CYPRESS = "cypress"

_TEMPLATE_BY_FRAMEWORK = {
    PLAYWRIGHT: "visual_regression_playwright.jinja2",
    CYPRESS: "visual_regression_cypress.jinja2",
}

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=(), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "screen"


def _build_cases(result: VisualComparisonResult, baseline_name: str) -> list[dict]:
    base_slug = _slugify(baseline_name)
    cases: list[dict] = []
    if not result.deltas:
        cases.append(
            {
                "test_name": f"regresja wizualna {base_slug} bez zmian",
                "description": "Brak wykrytych zmian - test pilnuje zgodnosci z baseline.",
                "baseline_filename": f"{base_slug}.png",
                "snapshot_name": base_slug,
            }
        )
        return cases

    for i, delta in enumerate(result.deltas, start=1):
        name = f"{base_slug}_{delta.change_type}_{i}"
        cases.append(
            {
                "test_name": f"regresja wizualna {name}",
                "description": f"[{delta.severity}] {delta.change_type}: {delta.description}",
                "baseline_filename": f"{name}.png",
                "snapshot_name": name,
            }
        )
    return cases


def generate_visual_regression_code(
    result: VisualComparisonResult,
    framework: str,
    baseline_name: str = "baseline",
    url: str = "/",
    threshold: float = 0.02,
) -> str:
    """Render visual-regression test code for ``framework`` (playwright|cypress)."""
    framework = framework.lower()
    template_name = _TEMPLATE_BY_FRAMEWORK.get(framework)
    if template_name is None:
        raise ValueError(
            f"Nieobslugiwany framework testow regresji wizualnej: '{framework}'. "
            f"Dostepne: {sorted(_TEMPLATE_BY_FRAMEWORK)}."
        )

    template = _env.get_template(template_name)
    return template.render(
        cases=_build_cases(result, baseline_name),
        suite_name=f"Regresja wizualna - {_slugify(baseline_name)}",
        url=url,
        threshold=threshold,
    )
