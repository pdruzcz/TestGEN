"""LLM-powered gap analyzer — Epic 5, Story 5.10.

Uses LLMGateway to perform semantic gap analysis between documentation
requirements and code entities. The LLM receives a structured prompt with
both lists and returns JSON-classified gaps.

Falls back gracefully when the LLM is unavailable or returns malformed data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.analysis.gap_analyzer import CodeEntity
from app.services.gap_analysis.comparator import (
    GapAnalysisSummaryData,
    GapFindingData,
    RequirementData,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a code-documentation gap analysis expert. Given a list of software requirements \
and a list of code entities (functions/classes extracted from source code), identify \
functional gaps between them.

Classify each gap as one of:
- "missing": requirement has no corresponding code implementation
- "different": code implementation diverges from the requirement specification
- "extra": code entity has no corresponding documentation/requirement
- "inconsistent": logical contradiction between requirement and code

Return ONLY valid JSON (no markdown fences) as a JSON array of objects with these fields:
{
  "requirement_id": "string or null",
  "code_entity_id": "string or null",
  "gap_type": "missing|different|extra|inconsistent",
  "description": "concise description of the gap",
  "match_score": 0.0-100.0,
  "severity": "critical|warning|info"
}
"""


class LLMGapAnalyzer:
    """Performs gap analysis using an LLM via LLMGateway."""

    def __init__(self, llm_gateway: Any | None = None):
        if llm_gateway is None:
            try:
                from app.services.analysis.llm_gateway import LLMGateway
                llm_gateway = LLMGateway()
            except Exception:
                logger.warning("LLMGateway not available")
                llm_gateway = None
        self.llm_gateway = llm_gateway

    async def analyze(
        self,
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
        provider: str = "anthropic",
        tenant_id: str | None = None,
    ) -> tuple[list[GapFindingData], GapAnalysisSummaryData]:
        """Run LLM gap analysis. Returns findings + summary."""
        findings: list[GapFindingData] = []

        if self.llm_gateway is None:
            logger.warning("LLMGateway unavailable, returning empty findings")
            return findings, self._empty_summary(requirements, code_entities)

        prompt = self._build_prompt(requirements, code_entities)
        if not prompt:
            return findings, self._empty_summary(requirements, code_entities)

        try:
            from app.services.analysis.llm_gateway import LLMMessage
        except ImportError:
            return findings, self._empty_summary(requirements, code_entities)

        try:
            response = await self.llm_gateway.complete(
                provider=provider,
                messages=[LLMMessage(role="user", content=prompt)],
                system_prompt=_SYSTEM_PROMPT,
                max_tokens=4000,
                temperature=0.0,
                module="gap_analysis",
                task_type="gap_llm",
                tenant_id=tenant_id,
            )
        except Exception as exc:
            logger.error("LLM gap analysis failed: %s", exc)
            return findings, self._empty_summary(requirements, code_entities)

        findings = self._parse_response(response.content, requirements, code_entities)

        summary = GapAnalysisSummaryData(
            total_requirements=len(requirements),
            total_code_entities=len(code_entities),
            missing_count=sum(1 for f in findings if f.gap_type == "missing"),
            different_count=sum(1 for f in findings if f.gap_type == "different"),
            extra_count=sum(1 for f in findings if f.gap_type == "extra"),
            inconsistent_count=sum(1 for f in findings if f.gap_type == "inconsistent"),
            avg_match_score=round(
                sum(f.match_score for f in findings) / len(findings), 1
            ) if findings else 0.0,
            coverage_percentage=round(
                100.0 - (sum(1 for f in findings if f.gap_type == "missing") /
                         max(len(requirements), 1)) * 100.0, 1
            ) if requirements else 0.0,
        )
        return findings, summary

    def _build_prompt(
        self,
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
    ) -> str:
        req_lines = []
        for r in requirements:
            req_lines.append(
                f"  - ID: {r.req_id} | Category: {r.category} | Priority: {r.priority} | "
                f"Text: {r.text}"
            )

        code_lines = []
        for ce in code_entities:
            code_lines.append(
                f"  - ID: {ce.name} | Type: {ce.type} | "
                f"File: {ce.file_path}:{ce.line_number} | Doc: {ce.docstring or 'N/A'}"
            )

        return (
            f"Requirements ({len(requirements)}):\n"
            + "\n".join(req_lines)
            + f"\n\nCode entities ({len(code_entities)}):\n"
            + "\n".join(code_lines)
            + "\n\nIdentify all functional gaps. Return a JSON array."
        )

    def _parse_response(
        self,
        content: str,
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
    ) -> list[GapFindingData]:
        try:
            items = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned non-JSON response")
            return []

        if not isinstance(items, list):
            return []

        req_map = {r.req_id: r for r in requirements}
        code_map = {ce.name: ce for ce in code_entities}

        findings: list[GapFindingData] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            gap_type = item.get("gap_type", "missing")
            if gap_type not in ("missing", "different", "extra", "inconsistent"):
                gap_type = "missing"

            req_id = item.get("requirement_id")
            code_id = item.get("code_entity_id")
            req = req_map.get(req_id)
            code = code_map.get(code_id) if code_id else None

            findings.append(GapFindingData(
                requirement_id=req_id,
                code_entity_id=code_id,
                gap_type=gap_type,
                description=item.get("description", "LLM-detected gap"),
                requirement_text=req.text if req else None,
                code_reference=f"{code.file_path}:{code.line_number}" if code else None,
                match_score=float(item.get("match_score", 50.0)),
                match_method="llm",
                context={"llm_generated": True},
                severity=item.get("severity", "warning"),
            ))
        return findings

    @staticmethod
    def _empty_summary(
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
    ) -> GapAnalysisSummaryData:
        return GapAnalysisSummaryData(
            total_requirements=len(requirements),
            total_code_entities=len(code_entities),
        )
