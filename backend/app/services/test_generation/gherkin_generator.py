"""Gherkin/BDD generator — Epic 3, Story 3.11.

Orchestrates the three engine modes:

- ``native`` — deterministic UML/GUI -> Gherkin mapping (:mod:`gherkin_mapper`)
  rendered with the ``gherkin_feature.jinja2`` template (AC-5),
- ``llm`` / ``hybrid`` — the native structure is enriched with natural-language
  step narration via the text-only LLM Gateway (AC-6); failures degrade back to
  the native result with a Polish warning,

plus structural validation (AC-7) whose problems are returned as *warnings*
(never blocking the save).
"""

import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.test_generation.gherkin_mapper import map_flows_to_feature
from app.services.test_generation.gherkin_models import GherkinFeatureModel

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=(), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

_GHERKIN_KEYWORDS = ("Given ", "When ", "Then ", "And ", "But ")


def render_feature(feature: GherkinFeatureModel) -> str:
    """Render a :class:`GherkinFeatureModel` to ``.feature`` text (AC-5)."""
    template = _env.get_template("gherkin_feature.jinja2")
    raw = template.render(feature=feature)
    # Collapse the runs of blank lines the template can leave behind.
    return re.sub(r"\n{3,}", "\n\n", raw).strip() + "\n"


def validate_gherkin(raw_feature: str, feature: GherkinFeatureModel) -> list[str]:
    """Return structural validation warnings (AC-7); never raises / blocks."""
    warnings: list[str] = []

    if "Feature:" not in raw_feature:
        warnings.append("Brak nagłówka Feature.")
    if not feature.scenarios:
        warnings.append("Feature nie zawiera żadnego scenariusza.")

    for scenario in feature.scenarios:
        keywords = {s.keyword for s in scenario.steps}
        if not scenario.steps:
            warnings.append(f"Scenariusz „{scenario.name}” nie ma kroków.")
            continue
        if "When" not in keywords and "Given" not in keywords:
            warnings.append(f"Scenariusz „{scenario.name}” nie ma kroku Given/When.")
        if "Then" not in keywords:
            warnings.append(f"Scenariusz „{scenario.name}” nie ma kroku Then.")
        for step in scenario.steps:
            if not step.text.strip():
                warnings.append(f"Pusty krok w scenariuszu „{scenario.name}”.")

        if scenario.is_outline:
            if not scenario.examples_rows:
                warnings.append(f"Scenario Outline „{scenario.name}” nie ma wierszy Examples.")
            placeholders = set(re.findall(r"<([^>]+)>", " ".join(s.text for s in scenario.steps)))
            missing = placeholders - set(scenario.examples_headers)
            if missing:
                warnings.append(
                    f"Scenario Outline „{scenario.name}”: brak kolumn Examples dla "
                    f"placeholderów: {', '.join(sorted(missing))}."
                )

    return warnings


def generate_native(flows: list, feature_name: str | None = None) -> tuple[GherkinFeatureModel, str, list[str]]:
    """Deterministic native generation (AC-5). Returns ``(model, raw, warnings)``."""
    feature = map_flows_to_feature(flows, feature_name)
    raw = render_feature(feature)
    warnings = validate_gherkin(raw, feature)
    return feature, raw, warnings


def _build_llm_prompt(feature: GherkinFeatureModel) -> str:
    lines = [
        "Jesteś ekspertem QA. Poniżej znajduje się szkic scenariuszy Gherkin/BDD "
        "wygenerowany z przepływu użytkownika.",
        "Wzbogać go o naturalne opisy kroków oraz realistyczne dane testowe, "
        "zachowując poprawną składnię Gherkin (Feature/Scenario/Given/When/Then).",
        "",
        render_feature(feature),
    ]
    return "\n".join(lines)


async def enrich_with_llm(
    feature: GherkinFeatureModel,
    raw_feature: str,
    llm_gateway,
    tenant_id=None,
) -> tuple[str, list[str]]:
    """Enrich the native ``.feature`` text via the LLM Gateway (AC-6).

    Returns ``(raw_feature, warnings)``. On any failure the native text is
    returned unchanged with an appended Polish warning (graceful degradation).
    """
    from app.services.analysis.llm_gateway import LLMMessage

    prompt = _build_llm_prompt(feature)
    try:
        response = await llm_gateway.complete(
            provider="anthropic",
            messages=[LLMMessage(role="user", content=prompt)],
            module="gherkin",
            task_type="gherkin_generation",
            tenant_id=tenant_id,
        )
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("LLM Gherkin enrichment failed: %s", exc)
        return raw_feature, ["Wzbogacenie LLM nie powiodło się — użyto wyniku natywnego."]

    enriched = (response.content or "").strip()
    if "Feature:" not in enriched:
        return raw_feature, ["Odpowiedź LLM nie zawierała poprawnego Feature — użyto wyniku natywnego."]
    return enriched + "\n", []
