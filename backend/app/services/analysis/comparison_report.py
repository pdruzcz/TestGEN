"""Comparison report module for Epic 2.

This module generates side-by-side comparison reports between native and LLM
analysis results, highlighting differences, accuracy metrics, and recommendations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.schemas.document import (
    DocumentStructure,
    ExtractedRequirementSchema,
)


@dataclass
class MetricComparison:
    """Comparison metric for a single feature."""

    feature_name: str
    native_value: float
    llm_value: float
    unit: str  # 'percentage', 'count', 'time_ms'
    delta: float
    better: str | None  # 'native', 'llm', or None if tie
    significance: str  # 'major', 'minor', 'none'


@dataclass
class RequirementComparison:
    """Comparison of a single requirement extraction."""

    requirement_id: str
    native_text: str | None
    llm_text: str | None
    native_confidence: float
    llm_confidence: float
    native_type: str | None
    llm_type: str | None
    similarity_score: float  # 0-1 similarity between texts
    match_status: str  # 'exact', 'similar', 'different', 'native_only', 'llm_only'


@dataclass
class FeatureComparison:
    """Comparison results for a single analysis feature."""

    feature_name: str
    story_id: str
    native_available: bool
    llm_available: bool
    metrics: list[MetricComparison]
    details: dict[str, Any]
    recommendation: str
    accuracy_native: float | None
    accuracy_llm: float | None
    winner: str | None  # 'native', 'llm', 'tie', 'hybrid'


@dataclass
class ComparisonReport:
    """Complete comparison report for native vs LLM analysis."""

    report_id: str
    document_name: str
    generated_at: datetime
    feature_comparisons: list[FeatureComparison]
    overall_metrics: dict[str, Any]
    summary: str
    recommendations: list[str]
    hybrid_strategy: dict[str, Any]


class ComparisonReportGenerator:
    """Generate comparison reports between native and LLM analysis.

    Compares results from native and LLM-based analysis modes for:
    - Requirement extraction
    - Classification
    - Glossary extraction
    - Inconsistency detection
    - Gap analysis
    - Test generation
    """

    def __init__(self) -> None:
        self.golden_data_path = "backend/tests/golden/epic2"

    def generate_report(
        self,
        doc: DocumentStructure,
        native_results: dict[str, Any],
        llm_results: dict[str, Any],
    ) -> ComparisonReport:
        """Generate comprehensive comparison report.

        Args:
            doc: Document structure
            native_results: Results from native analysis
            llm_results: Results from LLM analysis

        Returns:
            Comparison report with all feature comparisons
        """
        feature_comparisons: list[FeatureComparison] = []

        # Compare each feature
        feature_comparisons.append(
            self._compare_requirement_extraction(
                native_results.get("requirements"),
                llm_results.get("requirements"),
            )
        )

        feature_comparisons.append(
            self._compare_classification(
                native_results.get("classification"),
                llm_results.get("classification"),
            )
        )

        feature_comparisons.append(
            self._compare_glossary(
                native_results.get("glossary"),
                llm_results.get("glossary"),
            )
        )

        feature_comparisons.append(
            self._compare_inconsistencies(
                native_results.get("inconsistencies"),
                llm_results.get("inconsistencies"),
            )
        )

        feature_comparisons.append(
            self._compare_gap_analysis(
                native_results.get("gap_analysis"),
                llm_results.get("gap_analysis"),
            )
        )

        feature_comparisons.append(
            self._compare_test_generation(
                native_results.get("test_generation"),
                llm_results.get("test_generation"),
            )
        )

        # Calculate overall metrics
        overall_metrics = self._calculate_overall_metrics(feature_comparisons)

        # Generate summary
        summary = self._generate_summary(feature_comparisons, overall_metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(feature_comparisons)

        # Generate hybrid strategy
        hybrid_strategy = self._generate_hybrid_strategy(feature_comparisons)

        return ComparisonReport(
            report_id=str(uuid.uuid4()),
            document_name=doc.metadata.get("filename", "Unknown"),
            generated_at=datetime.utcnow(),
            feature_comparisons=feature_comparisons,
            overall_metrics=overall_metrics,
            summary=summary,
            recommendations=recommendations,
            hybrid_strategy=hybrid_strategy,
        )

    def _compare_requirement_extraction(
        self,
        native_reqs: list[ExtractedRequirementSchema] | None,
        llm_reqs: list[ExtractedRequirementSchema] | None,
    ) -> FeatureComparison:
        """Compare requirement extraction results."""
        native_count = len(native_reqs) if native_reqs else 0
        llm_count = len(llm_reqs) if llm_reqs else 0

        # Calculate metrics
        metrics = [
            MetricComparison(
                feature_name="requirement_extraction",
                native_value=float(native_count),
                llm_value=float(llm_count),
                unit="count",
                delta=abs(native_count - llm_count),
                better="native" if native_count > llm_count else "llm" if llm_count > native_count else None,
                significance="major" if abs(native_count - llm_count) > 2 else "minor",
            ),
            MetricComparison(
                feature_name="avg_confidence",
                native_value=self._calc_avg_confidence(native_reqs),
                llm_value=self._calc_avg_confidence(llm_reqs),
                unit="percentage",
                delta=0,
                better=None,
                significance="none",
            ),
        ]

        # Compare individual requirements
        requirement_comparisons = self._compare_requirements_list(native_reqs, llm_reqs)

        details = {
            "requirement_comparisons": [
                {
                    "requirement_id": rc.requirement_id,
                    "similarity": rc.similarity_score,
                    "match_status": rc.match_status,
                }
                for rc in requirement_comparisons
            ],
            "native_only": len([rc for rc in requirement_comparisons if rc.match_status == "native_only"]),
            "llm_only": len([rc for rc in requirement_comparisons if rc.match_status == "llm_only"]),
            "exact_matches": len([rc for rc in requirement_comparisons if rc.match_status == "exact"]),
        }

        return FeatureComparison(
            feature_name="requirement_extraction",
            story_id="2.4",
            native_available=native_reqs is not None,
            llm_available=llm_reqs is not None,
            metrics=metrics,
            details=details,
            recommendation=self._req_extraction_recommendation(details),
            accuracy_native=None,
            accuracy_llm=None,
            winner=self._determine_winner(details),
        )

    def _compare_classification(
        self,
        native_classification: dict[str, Any] | None,
        llm_classification: dict[str, Any] | None,
    ) -> FeatureComparison:
        """Compare document classification results."""
        metrics = []
        details = {}

        if native_classification and llm_classification:
            # Compare document type
            type_match = native_classification.get("document_type") == llm_classification.get("document_type")

            metrics.append(
                MetricComparison(
                    feature_name="document_type_match",
                    native_value=1.0 if type_match else 0.0,
                    llm_value=1.0 if type_match else 0.0,
                    unit="percentage",
                    delta=0.0,
                    better=None,
                    significance="major" if not type_match else "none",
                )
            )

            # Compare confidence
            native_conf = native_classification.get("confidence", 0)
            llm_conf = llm_classification.get("confidence", 0)

            metrics.append(
                MetricComparison(
                    feature_name="confidence",
                    native_value=native_conf,
                    llm_value=llm_conf,
                    unit="percentage",
                    delta=abs(native_conf - llm_conf),
                    better="native" if native_conf > llm_conf else "llm",
                    significance="major" if abs(native_conf - llm_conf) > 10 else "minor",
                )
            )

            details = {
                "type_match": type_match,
                "native_type": native_classification.get("document_type"),
                "llm_type": llm_classification.get("document_type"),
                "confidence_diff": abs(native_conf - llm_conf),
            }

        return FeatureComparison(
            feature_name="classification",
            story_id="2.3",
            native_available=native_classification is not None,
            llm_available=llm_classification is not None,
            metrics=metrics,
            details=details,
            recommendation="Użyj LLM dla niepewnych klasyfikacji, native dla szybkiego wstępnego filtrowania",
            accuracy_native=None,
            accuracy_llm=None,
            winner="hybrid",
        )

    def _compare_glossary(
        self,
        native_glossary: dict[str, Any] | None,
        llm_glossary: dict[str, Any] | None,
    ) -> FeatureComparison:
        """Compare glossary extraction results."""
        native_terms = len(native_glossary.get("terms", [])) if native_glossary else 0
        llm_terms = len(llm_glossary.get("terms", [])) if llm_glossary else 0

        metrics = [
            MetricComparison(
                feature_name="terms_extracted",
                native_value=float(native_terms),
                llm_value=float(llm_terms),
                unit="count",
                delta=abs(native_terms - llm_terms),
                better="llm" if llm_terms > native_terms else "native",
                significance="minor",
            ),
        ]

        details = {
            "native_terms": native_terms,
            "llm_terms": llm_terms,
            "overlap": 0,  # Would need detailed comparison
        }

        return FeatureComparison(
            feature_name="glossary_extraction",
            story_id="2.6",
            native_available=native_glossary is not None,
            llm_available=llm_glossary is not None,
            metrics=metrics,
            details=details,
            recommendation="LLM lepiej wyekstrahuje terminologię z kontekstu",
            accuracy_native=None,
            accuracy_llm=None,
            winner="llm",
        )

    def _compare_inconsistencies(
        self,
        native_inconsistencies: list[Any] | None,
        llm_inconsistencies: list[Any] | None,
    ) -> FeatureComparison:
        """Compare inconsistency detection results."""
        native_count = len(native_inconsistencies) if native_inconsistencies else 0
        llm_count = len(llm_inconsistencies) if llm_inconsistencies else 0

        metrics = [
            MetricComparison(
                feature_name="inconsistencies_found",
                native_value=float(native_count),
                llm_value=float(llm_count),
                unit="count",
                delta=abs(native_count - llm_count),
                better=None,
                significance="minor",
            ),
        ]

        details = {
            "native_count": native_count,
            "llm_count": llm_count,
            "severity_breakdown_native": {},
            "severity_breakdown_llm": {},
        }

        if native_inconsistencies:
            for inc in native_inconsistencies:
                sev = inc.get("severity", "unknown")
                details["severity_breakdown_native"][sev] = details["severity_breakdown_native"].get(sev, 0) + 1

        if llm_inconsistencies:
            for inc in llm_inconsistencies:
                sev = inc.get("severity", "unknown")
                details["severity_breakdown_llm"][sev] = details["severity_breakdown_llm"].get(sev, 0) + 1

        return FeatureComparison(
            feature_name="inconsistency_detection",
            story_id="2.7",
            native_available=native_inconsistencies is not None,
            llm_available=llm_inconsistencies is not None,
            metrics=metrics,
            details=details,
            recommendation="Native dla wzorców, LLM dla semantycznych sprzeczności - użyj obu",
            accuracy_native=None,
            accuracy_llm=None,
            winner="hybrid",
        )

    def _compare_gap_analysis(
        self,
        native_gap: dict[str, Any] | None,
        llm_gap: dict[str, Any] | None,
    ) -> FeatureComparison:
        """Compare gap analysis results."""
        metrics = []
        details = {}

        if native_gap and llm_gap:
            native_coverage = native_gap.get("coverage_percentage", 0)
            llm_coverage = llm_gap.get("coverage_percentage", 0)

            metrics.append(
                MetricComparison(
                    feature_name="coverage_percentage",
                    native_value=native_coverage,
                    llm_value=llm_coverage,
                    unit="percentage",
                    delta=abs(native_coverage - llm_coverage),
                    better="native" if native_coverage > llm_coverage else "llm",
                    significance="minor",
                )
            )

            details = {
                "native_coverage": native_coverage,
                "llm_coverage": llm_coverage,
                "native_critical_gaps": len(native_gap.get("critical_gaps", [])),
                "llm_critical_gaps": len(llm_gap.get("critical_gaps", [])),
            }

        return FeatureComparison(
            feature_name="gap_analysis",
            story_id="2.8",
            native_available=native_gap is not None,
            llm_available=llm_gap is not None,
            metrics=metrics,
            details=details,
            recommendation="LLM lepszy w dopasowywaniu semantycznym, native w precyzyjnym dopasowaniu nazw",
            accuracy_native=None,
            accuracy_llm=None,
            winner="hybrid",
        )

    def _compare_test_generation(
        self,
        native_tests: dict[str, Any] | None,
        llm_tests: dict[str, Any] | None,
    ) -> FeatureComparison:
        """Compare test generation results."""
        native_count = native_tests.get("generated_tests", 0) if native_tests else 0
        llm_count = llm_tests.get("generated_tests", 0) if llm_tests else 0

        metrics = [
            MetricComparison(
                feature_name="tests_generated",
                native_value=float(native_count),
                llm_value=float(llm_count),
                unit="count",
                delta=abs(native_count - llm_count),
                better="llm" if llm_count > native_count else "native",
                significance="major",
            ),
        ]

        details = {
            "native_count": native_count,
            "llm_count": llm_count,
            "automation_feasibility_native": {},
            "automation_feasibility_llm": {},
        }

        if native_tests and native_tests.get("statistics"):
            stats = native_tests["statistics"].get("by_automation_feasibility", {})
            details["automation_feasibility_native"] = stats

        if llm_tests and llm_tests.get("statistics"):
            stats = llm_tests["statistics"].get("by_automation_feasibility", {})
            details["automation_feasibility_llm"] = stats

        return FeatureComparison(
            feature_name="test_generation",
            story_id="2.10",
            native_available=native_tests is not None,
            llm_available=llm_tests is not None,
            metrics=metrics,
            details=details,
            recommendation="LLM generuje więcej i bardziej szczegółowe testy",
            accuracy_native=None,
            accuracy_llm=None,
            winner="llm",
        )

    def _calc_avg_confidence(self, reqs: list[ExtractedRequirementSchema] | None) -> float:
        """Calculate average confidence from requirements."""
        if not reqs:
            return 0.0
        confidences = [r.get("confidence", 0) for r in reqs]
        return sum(confidences) / len(confidences) if confidences else 0.0

    def _compare_requirements_list(
        self,
        native_reqs: list[ExtractedRequirementSchema] | None,
        llm_reqs: list[ExtractedRequirementSchema] | None,
    ) -> list[RequirementComparison]:
        """Compare individual requirements."""
        comparisons: list[RequirementComparison] = []

        if not native_reqs and not llm_reqs:
            return comparisons

        native_dict = {r["req_id"]: r for r in (native_reqs or [])}
        llm_dict = {r["req_id"]: r for r in (llm_reqs or [])}

        all_ids = set(native_dict.keys()) | set(llm_dict.keys())

        for req_id in all_ids:
            native_req = native_dict.get(req_id)
            llm_req = llm_dict.get(req_id)

            if native_req and llm_req:
                # Both extracted - compare
                similarity = self._calculate_text_similarity(
                    native_req.get("text", ""),
                    llm_req.get("text", ""),
                )
                match_status = (
                    "exact" if similarity > 0.95 else "similar" if similarity > 0.7 else "different"
                )
            elif native_req:
                similarity = 0.0
                match_status = "native_only"
            else:
                similarity = 0.0
                match_status = "llm_only"

            comparisons.append(
                RequirementComparison(
                    requirement_id=req_id,
                    native_text=native_req.get("text") if native_req else None,
                    llm_text=llm_req.get("text") if llm_req else None,
                    native_confidence=native_req.get("confidence", 0) if native_req else 0,
                    llm_confidence=llm_req.get("confidence", 0) if llm_req else 0,
                    native_type=native_req.get("type") if native_req else None,
                    llm_type=llm_req.get("type") if llm_req else None,
                    similarity_score=similarity,
                    match_status=match_status,
                )
            )

        return comparisons

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using word overlap."""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _req_extraction_recommendation(self, details: dict[str, Any]) -> str:
        """Generate recommendation for requirement extraction."""
        exact = details.get("exact_matches", 0)
        total = details.get("requirement_comparisons", [])
        total_count = len(total) if total else 1

        if exact / total_count > 0.8:
            "Native i LLM zgadzają się - użyj wyników hybrydowych"
        elif details.get("llm_only", 0) > details.get("native_only", 0):
            return "LLM wykrywa więcej wymagań - rozważ użycie LLM"
        else:
            return "Native wykrywa unikalne wymagania - użyj podejścia hybrydowego"

    def _determine_winner(self, details: dict[str, Any]) -> str:
        """Determine winner for requirement extraction."""
        if details.get("exact_matches", 0) > 3:
            return "tie"
        elif details.get("llm_only", 0) > details.get("native_only", 0):
            return "llm"
        else:
            return "native"

    def _calculate_overall_metrics(
        self, comparisons: list[FeatureComparison]
    ) -> dict[str, Any]:
        """Calculate overall comparison metrics."""
        native_wins = len([c for c in comparisons if c.winner == "native"])
        llm_wins = len([c for c in comparisons if c.winner == "llm"])
        hybrids = len([c for c in comparisons if c.winner == "hybrid"])
        ties = len([c for c in comparisons if c.winner == "tie"])

        return {
            "total_features": len(comparisons),
            "native_wins": native_wins,
            "llm_wins": llm_wins,
            "hybrid_recommended": hybrids,
            "ties": ties,
            "native_available": len([c for c in comparisons if c.native_available]),
            "llm_available": len([c for c in comparisons if c.llm_available]),
        }

    def _generate_summary(
        self, comparisons: list[FeatureComparison], metrics: dict[str, Any]
    ) -> str:
        """Generate executive summary."""
        total = metrics["total_features"]
        native_wins = metrics["native_wins"]
        llm_wins = metrics["llm_wins"]
        hybrids = metrics["hybrid_recommended"]

        summary_parts = [
            f"Porównano {total} funkcji analizy dokumentacji.",
        ]

        if native_wins > 0:
            summary_parts.append(f"Native przewyższa LLM w {native_wins} funkcjach.")

        if llm_wins > 0:
            summary_parts.append(f"LLM przewyższa Native w {llm_wins} funkcjach.")

        if hybrids > 0:
            summary_parts.append(f"{hybrids} funkcjach zaleca się podejście hybrydowe.")

        return " ".join(summary_parts)

    def _generate_recommendations(
        self, comparisons: list[FeatureComparison]
    ) -> list[str]:
        """Generate overall recommendations."""
        recommendations = [
            "Używaj trybu native dla szybkiego, wstępnego przetwarzania dokumentów",
            "Używaj trybu LLM dla złożonych dokumentów i niestandardowych formatów",
            "Rozważ podejście hybrydowe: native dla wstępnej analizy, LLM dla szczegółów",
            "Waliduj wyniki LLM używając wzorców native dla kluczowych wymagań",
        ]

        # Add feature-specific recommendations
        for comp in comparisons:
            if comp.recommendation and comp.recommendation not in recommendations:
                recommendations.append(comp.recommendation)

        return recommendations

    def _generate_hybrid_strategy(
        self, comparisons: list[FeatureComparison]
    ) -> dict[str, Any]:
        """Generate hybrid strategy recommendations."""
        strategy = {
            "recommended_mode": "hybrid",
            "feature_modes": {},
            "rationale": [],
        }

        for comp in comparisons:
            if comp.winner == "native":
                strategy["feature_modes"][comp.feature_name] = "native"
                strategy["rationale"].append(f"{comp.feature_name}: Native daje lepsze wyniki")
            elif comp.winner == "llm":
                strategy["feature_modes"][comp.feature_name] = "llm"
                strategy["rationale"].append(f"{comp.feature_name}: LLM daje lepsze wyniki")
            else:
                strategy["feature_modes"][comp.feature_name] = "hybrid"
                strategy["rationale"].append(f"{comp.feature_name}: Zalecane podejście hybrydowe")

        return strategy


def generate_comparison_report(
    doc: DocumentStructure,
    native_results: dict[str, Any],
    llm_results: dict[str, Any],
) -> ComparisonReport:
    """Convenience function to generate comparison report.

    Args:
        doc: Document structure
        native_results: Results from native analysis
        llm_results: Results from LLM analysis

    Returns:
        Comparison report
    """
    generator = ComparisonReportGenerator()
    return generator.generate_report(doc, native_results, llm_results)
