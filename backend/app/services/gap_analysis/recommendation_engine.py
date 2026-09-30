"""Recommendation generation engine — Epic 5, Story 5.5.

Template-based (native) recommendation generator.  Converts gap findings
and code errors into actionable recommendations with:
  - Priority mapping (P1–P4) based on gap_type/severity/category
  - Confidence score (0.0–1.0) derived from match_score / rule certainty
  - Human-readable title, description and suggestion

Designed to be extensible — Story 5.10 will add an LLM-based path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.code_error import CodeError, ErrorCategory
from app.models.gap_finding import GapFinding, GapType
from app.models.recommendation import RecommendationPriority


@dataclass
class GeneratedRecommendation:
    """Intermediate representation — converted to Recommendation ORM by task."""

    title: str
    description: str
    priority: RecommendationPriority
    confidence: float
    source_type: str  # "gap_finding" | "code_error"
    source_ref: str | None = None
    suggestion: str | None = None
    gap_finding_id: str | None = None
    code_error_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


# ── Priority + confidence maps ───────────────────────────────────────────────

_GAP_PRIORITY: dict[GapType, RecommendationPriority] = {
    GapType.INCONSISTENT: RecommendationPriority.P1,
    GapType.MISSING: RecommendationPriority.P1,
    GapType.DIFFERENT: RecommendationPriority.P2,
    GapType.EXTRA: RecommendationPriority.P4,
}

# Severity boosts confidence for gap-based recommendations
_GAP_SEVERITY_CONFIDENCE: dict[str, float] = {
    "critical": 0.9,
    "warning": 0.7,
    "info": 0.4,
}

_CODE_ERROR_PRIORITY: dict[ErrorCategory, RecommendationPriority] = {
    ErrorCategory.SYNTAX: RecommendationPriority.P1,
    ErrorCategory.LOGIC: RecommendationPriority.P2,
    ErrorCategory.SEMANTIC: RecommendationPriority.P3,
    ErrorCategory.CONFORMANCE: RecommendationPriority.P3,
}

_CODE_ERROR_SEVERITY_CONFIDENCE: dict[str, float] = {
    "critical": 0.95,
    "warning": 0.7,
    "info": 0.4,
}


# ── Template text (Polish) ───────────────────────────────────────────────────

_GAP_TEMPLATES: dict[GapType, dict[str, str]] = {
    GapType.MISSING: {
        "title": "Brak implementacji wymagania",
        "description": "Wymaganie '{req}' nie ma odpowiadającej implementacji w kodzie.",
        "suggestion": "Dodaj funkcję lub metodę realizującą to wymaganie. "
        "Oznacz ją w kodzie tak, aby powiązanie z wymaganie było możliwe do zweryfikowania.",
    },
    GapType.DIFFERENT: {
        "title": "Implementacja różni się od specyfikacji",
        "description": "Implementacja wymagania '{req}' odbiega od opisanego zachowania.",
        "suggestion": "Porównaj treść wymagania z implementacją i dostosuj kod "
        "lub zaktualizuj dokumentację.",
    },
    GapType.EXTRA: {
        "title": "Kod bez powiązania z wymaganiami",
        "description": "Fragment kodu '{entity}' nie ma odpowiednika w dokumentacji.",
        "suggestion": "Uzupełnij dokumentację o ten wymóg lub usuń niepotrzebny kod.",
    },
    GapType.INCONSISTENT: {
        "title": "Niespójność między wymaganiami",
        "description": "Wykryto sprzeczność dotyczącą '{req}'.",
        "suggestion": "Przejrzyj powiązane wymagania i usuń sprzeczność "
        "w dokumentacji lub kodzie.",
    },
}

_CODE_ERROR_TEMPLATES: dict[ErrorCategory, dict[str, str]] = {
    ErrorCategory.SYNTAX: {
        "title": "Błąd składni",
        "suggestion": "Napraw błąd składni — kod nie kompiluje się poprawnie.",
    },
    ErrorCategory.LOGIC: {
        "title": "Problem logiczny w kodzie",
        "suggestion": "Przejrzyj logikę funkcji i rozważ refaktoryzację.",
    },
    ErrorCategory.SEMANTIC: {
        "title": "Problem semantyczny w kodzie",
        "suggestion": "Dodaj brakujące adnotacje typów, aby poprawić czytelność "
        "i bezpieczeństwo typów.",
    },
    ErrorCategory.CONFORMANCE: {
        "title": "Naruszenie konwencji kodowania",
        "suggestion": "Dostosuj kod do konwencji projektu (docstring, nazewnictwo).",
    },
}


class RecommendationEngine:
    """Generate recommendations from gap findings and code errors."""

    def generate_from_gap_findings(
        self,
        findings: list[GapFinding],
    ) -> list[GeneratedRecommendation]:
        """Convert gap findings into prioritised recommendations."""
        recommendations: list[GeneratedRecommendation] = []

        for f in findings:
            template = _GAP_TEMPLATES.get(f.gap_type, _GAP_TEMPLATES[GapType.DIFFERENT])
            priority = _GAP_PRIORITY.get(f.gap_type, RecommendationPriority.P3)

            # Confidence: blend severity with match_score
            sev_conf = _GAP_SEVERITY_CONFIDENCE.get(f.severity or "warning", 0.6)
            score_conf = max(0.0, min(1.0, 1.0 - f.match_score / 100.0))
            confidence = round((sev_conf * 0.6 + score_conf * 0.4), 2)

            req_ref = f.requirement_id or f.code_entity_id or "nieznane"
            entity_ref = f.code_entity_id or f.code_reference or "nieznane"

            if f.gap_type == GapType.MISSING:
                desc = template["description"].format(req=req_ref)
                ref = f"requirement={req_ref}"
            elif f.gap_type == GapType.EXTRA:
                desc = template["description"].format(entity=entity_ref)
                ref = f"entity={entity_ref}"
            else:
                desc = template["description"].format(req=req_ref)
                ref = f"requirement={req_ref}"

            recommendations.append(
                GeneratedRecommendation(
                    title=template["title"],
                    description=desc,
                    priority=priority,
                    confidence=confidence,
                    source_type="gap_finding",
                    source_ref=ref,
                    suggestion=template["suggestion"],
                    gap_finding_id=str(f.id) if hasattr(f, "id") else None,
                    context={
                        "gap_type": f.gap_type.value,
                        "severity": f.severity,
                        "match_score": f.match_score,
                    },
                )
            )

        return recommendations

    def generate_from_code_errors(
        self,
        errors: list[CodeError],
    ) -> list[GeneratedRecommendation]:
        """Convert code errors into prioritised recommendations."""
        recommendations: list[GeneratedRecommendation] = []

        for e in errors:
            template = _CODE_ERROR_TEMPLATES.get(
                e.category, _CODE_ERROR_TEMPLATES[ErrorCategory.LOGIC]
            )
            priority = _CODE_ERROR_PRIORITY.get(
                e.category, RecommendationPriority.P3
            )

            sev_conf = _CODE_ERROR_SEVERITY_CONFIDENCE.get(
                e.severity or "warning", 0.6
            )
            # Rule-based confidence: deterministic rules get higher base
            rule_conf = 0.85 if e.rule_id and e.rule_id.startswith("SYNTAX") else 0.65
            confidence = round((sev_conf * 0.5 + rule_conf * 0.5), 2)

            loc = f" ({e.file_path}:{e.line_start})" if e.file_path else ""

            recommendations.append(
                GeneratedRecommendation(
                    title=template["title"],
                    description=f"{e.message}{loc}",
                    priority=priority,
                    confidence=confidence,
                    source_type="code_error",
                    source_ref=f"rule={e.rule_id}" if e.rule_id else None,
                    suggestion=e.suggestion or template["suggestion"],
                    code_error_id=str(e.id) if hasattr(e, "id") else None,
                    context={
                        "category": (
                            e.category.value
                            if hasattr(e.category, "value")
                            else str(e.category)
                        ),
                        "severity": e.severity,
                        "rule_id": e.rule_id,
                        "file_path": e.file_path,
                        "line_start": e.line_start,
                    },
                )
            )

        return recommendations

    def generate(
        self,
        findings: list[GapFinding] | None = None,
        code_errors: list[CodeError] | None = None,
    ) -> list[GeneratedRecommendation]:
        """Generate all recommendations, sorted by priority then confidence."""
        recs: list[GeneratedRecommendation] = []

        if findings:
            recs.extend(self.generate_from_gap_findings(findings))
        if code_errors:
            recs.extend(self.generate_from_code_errors(code_errors))

        # Sort: P1 first, then P2, etc.; within same priority, higher confidence first
        priority_order = {
            RecommendationPriority.P1: 0,
            RecommendationPriority.P2: 1,
            RecommendationPriority.P3: 2,
            RecommendationPriority.P4: 3,
        }
        recs.sort(
            key=lambda r: (priority_order.get(r.priority, 9), -r.confidence)
        )
        return recs
