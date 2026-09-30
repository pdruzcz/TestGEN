"""Pure-Python Gherkin structures — Epic 3, Story 3.11.

Framework-agnostic dataclasses describing a Gherkin ``.feature`` (feature ->
scenarios -> steps, plus optional Background and Scenario Outline Examples).
These are produced by :mod:`gherkin_mapper`, rendered by the Jinja2 template in
:mod:`gherkin_generator` and validated by ``validate_gherkin``.
"""

from dataclasses import dataclass, field

# Gherkin step keywords.
GIVEN = "Given"
WHEN = "When"
THEN = "Then"
AND = "And"


@dataclass
class GherkinStep:
    keyword: str  # Given | When | Then | And
    text: str

    def to_dict(self) -> dict:
        return {"keyword": self.keyword, "text": self.text}


@dataclass
class GherkinScenario:
    name: str
    steps: list[GherkinStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    # When ``examples`` is non-empty the scenario is rendered as a Scenario Outline.
    examples_headers: list[str] = field(default_factory=list)
    examples_rows: list[list[str]] = field(default_factory=list)

    @property
    def is_outline(self) -> bool:
        return bool(self.examples_headers)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tags": self.tags,
            "steps": [s.to_dict() for s in self.steps],
            "examples_headers": self.examples_headers,
            "examples_rows": self.examples_rows,
        }


@dataclass
class GherkinFeatureModel:
    feature_name: str
    feature_description: str = ""
    background_steps: list[GherkinStep] = field(default_factory=list)
    scenarios: list[GherkinScenario] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feature_name": self.feature_name,
            "feature_description": self.feature_description,
            "tags": self.tags,
            "background_steps": [s.to_dict() for s in self.background_steps],
            "scenarios": [s.to_dict() for s in self.scenarios],
        }
