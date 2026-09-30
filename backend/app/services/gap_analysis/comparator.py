"""ComparatorService — fuzzy matching engine for functional gap analysis.

Epic 5, Story 5.1.

Implements three matching algorithms in pure Python (no external deps):
- Levenshtein distance
- Jaro-Winkler similarity
- TF-IDF cosine similarity

Each algorithm returns a score 0-100. Scores are combined with weights
(Levenshtein 0.25, Jaro-Winkler 0.35, Semantic 0.40) into a final match_score.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.services.analysis.gap_analyzer import CodeEntity


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class GapFindingData:
    """In-memory representation of a gap finding (before ORM persistence)."""

    requirement_id: str | None
    code_entity_id: str | None
    gap_type: str  # "missing", "different", "extra", "inconsistent"
    description: str
    requirement_text: str | None = None
    code_reference: str | None = None
    match_score: float = 0.0
    match_method: str = "combined"
    context: dict[str, Any] = field(default_factory=dict)
    severity: str = "warning"


@dataclass
class GapAnalysisSummaryData:
    """Aggregate summary of a gap analysis run."""

    total_requirements: int = 0
    total_code_entities: int = 0
    missing_count: int = 0
    different_count: int = 0
    extra_count: int = 0
    inconsistent_count: int = 0
    avg_match_score: float = 0.0
    coverage_percentage: float = 0.0


@dataclass
class RequirementData:
    """Simplified requirement for comparison."""

    req_id: str
    text: str
    category: str = ""
    priority: str = "medium"
    source_section_id: str | None = None


# ── Pure-Python fuzzy matching algorithms ────────────────────────────────────


_STOP_WORDS_PL = frozenset({
    "musi", "powinien", "może", "ma", "jest", "dla", "przez", "do",
    "z", "w", "na", "lub", "oraz", "nie", "się", "niech", "są",
    "the", "a", "an", "is", "are", "must", "should", "may", "can",
    "be", "to", "of", "in", "for", "with", "and", "or", "not",
})


def _normalize(name: str) -> str:
    """Lowercase and strip non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Classic Levenshtein distance (dynamic programming)."""
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            cost = 0 if c1 == c2 else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _levenshtein_match(req_name: str, code_name: str) -> float:
    """Return 0-100 similarity score based on Levenshtein distance."""
    a = _normalize(req_name)
    b = _normalize(code_name)
    if not a or not b:
        return 0.0
    max_len = max(len(a), len(b))
    dist = _levenshtein_distance(a, b)
    return max(0.0, 100.0 * (1.0 - dist / max_len))


def _jaro_similarity(s1: str, s2: str) -> float:
    """Jaro similarity (0-1)."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    match_dist = max(len(s1), len(s2)) // 2 - 1
    match_dist = max(0, match_dist)

    s1_matches = [False] * len(s1)
    s2_matches = [False] * len(s2)
    matches = 0

    for i, c in enumerate(s1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len(s2))
        for j in range(start, end):
            if s2_matches[j] or s2[j] != c:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i, matched in enumerate(s1_matches):
        if not matched:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    transpositions //= 2
    m = matches
    return (m / len(s1) + m / len(s2) + (m - transpositions) / m) / 3.0


def _jaro_winkler_match(req_name: str, code_name: str) -> float:
    """Jaro-Winkler similarity (0-100) with prefix boost."""
    a = req_name.lower().strip()
    b = code_name.lower().strip()
    jaro = _jaro_similarity(a, b)
    # Winkler prefix boost: up to 4 matching prefix chars
    prefix_len = 0
    for ca, cb in zip(a, b, strict=False):
        if ca == cb and prefix_len < 4:
            prefix_len += 1
        else:
            break
    jw = jaro + prefix_len * 0.1 * (1.0 - jaro)
    return jw * 100.0


def _tokenize(text: str) -> list[str]:
    """Tokenize text for TF-IDF: lowercase, split, remove stop words."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS_PL]


def _tfidf_cosine_match(req_text: str, code_text: str) -> float:
    """TF-IDF cosine similarity (0-100).

    Uses simple term-frequency weighting with inverse document frequency
    approximated from the two documents.
    """
    tokens_a = _tokenize(req_text)
    tokens_b = _tokenize(code_text)
    if not tokens_a or not tokens_b:
        return 0.0

    # Term frequencies
    tf_a = Counter(tokens_a)
    tf_b = Counter(tokens_b)

    # IDF approximation: documents = {doc_a, doc_b}
    all_terms = set(tf_a) | set(tf_b)
    idf: dict[str, float] = {}
    for term in all_terms:
        doc_count = (1 if term in tf_a else 0) + (1 if term in tf_b else 0)
        idf[term] = math.log(1.0 + 2.0 / doc_count) if doc_count > 0 else 0.0

    # TF-IDF vectors
    vec_a = {t: tf_a.get(t, 0) * idf[t] for t in all_terms}
    vec_b = {t: tf_b.get(t, 0) * idf[t] for t in all_terms}

    # Cosine similarity
    dot = sum(vec_a[t] * vec_b[t] for t in all_terms)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    cosine = dot / (norm_a * norm_b)
    return max(0.0, min(100.0, cosine * 100.0))


def _combine_scores(lev: float, jw: float, sem: float) -> float:
    """Weighted average: Levenshtein 0.25, Jaro-Winkler 0.35, Semantic 0.40."""
    return lev * 0.25 + jw * 0.35 + sem * 0.40


# ── ComparatorService ────────────────────────────────────────────────────────


# Thresholds
_MATCH_THRESHOLD = 50.0  # below this → no match (gap = missing)
_DIVERGENT_THRESHOLD = 70.0  # 50-70 → divergent (different)

# Weight for combine
_WEIGHTS = {"levenshtein": 0.25, "jaro_winkler": 0.35, "semantic": 0.40}


class ComparatorService:
    """Service that compares documentation requirements against code entities."""

    def __init__(self) -> None:
        self.match_threshold: float = _MATCH_THRESHOLD
        self.divergent_threshold: float = _DIVERGENT_THRESHOLD

    def compare(
        self,
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
    ) -> tuple[list[GapFindingData], GapAnalysisSummaryData]:
        """Compare requirements against code entities.

        Phase 1: Score each requirement against each code entity.
        Phase 2: Delegate classification to GapClassifier.
        Phase 3: Build aggregate summary.

        Returns a list of gap findings and an aggregate summary.
        """
        from app.services.gap_analysis.classifier import (
            EntityMapping,
            GapClassifier,
        )

        total_reqs = len(requirements)
        total_code = len(code_entities)

        # Phase 1: Score all requirement-entity pairs
        mappings: list[EntityMapping] = []
        all_scores: dict[str, dict[str, float]] = {}
        match_scores: list[float] = []

        for req in requirements:
            best_entity: CodeEntity | None = None
            best_score = 0.0
            best_method = "combined"
            req_scores: dict[str, float] = {}

            for entity in code_entities:
                lev = _levenshtein_match(req.text, entity.name)
                jw = _jaro_winkler_match(req.text, entity.name)

                code_text = entity.name
                if entity.docstring:
                    code_text += " " + entity.docstring
                sem = _tfidf_cosine_match(req.text, code_text)

                combined = _combine_scores(lev, jw, sem)
                req_scores[entity.entity_id] = combined

                if combined > best_score:
                    best_score = combined
                    best_entity = entity
                    best_method = "combined"

            all_scores[req.req_id] = req_scores
            mappings.append(EntityMapping(
                requirement=req,
                best_entity=best_entity,
                best_score=best_score,
                match_method=best_method,
            ))
            if best_entity and best_score >= self.match_threshold:
                match_scores.append(best_score)

        # Phase 2: Classify using GapClassifier
        classifier = GapClassifier()
        findings, type_summary = classifier.classify(
            mappings, requirements, code_entities, all_scores
        )

        # Phase 3: Build aggregate summary
        missing_count = type_summary["missing"].count
        different_count = type_summary["different"].count
        extra_count = type_summary["extra"].count
        inconsistent_count = type_summary["inconsistent"].count

        matched_reqs = total_reqs - missing_count - different_count
        coverage = (matched_reqs / total_reqs * 100.0) if total_reqs > 0 else 0.0
        avg_score = sum(match_scores) / len(match_scores) if match_scores else 0.0

        summary = GapAnalysisSummaryData(
            total_requirements=total_reqs,
            total_code_entities=total_code,
            missing_count=missing_count,
            different_count=different_count,
            extra_count=extra_count,
            inconsistent_count=inconsistent_count,
            avg_match_score=round(avg_score, 1),
            coverage_percentage=round(coverage, 1),
        )

        return findings, summary
