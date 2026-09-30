"""Real code-structure provider for diagram↔code comparison (Story 3.4 closure).

The source of truth for code structure is Epic 1's ``logic_structures`` AST
analysis (``AnalysisResult.module == "logic_structures"``), already wired into
the documentation module (E2). ``LogicStructuresCodeProvider`` reuses that
payload to supply the code-side ``CodeClass``/``CodeInterface`` structures that
``DiagramCodeComparator`` compares a class diagram against.

The ``ICodeStructureProvider`` protocol is synchronous, so the provider resolves
the ``logic_structures`` payload up front via ``load()`` (async — mirrors the
``document_tasks`` query) and serves the synchronous getters by mapping the
cached payload. ``StubCodeStructureProvider`` remains as a test/fallback for
projects without a ``logic_structures`` analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.uml.class_code_comparator import (
    CodeAttribute,
    CodeClass,
    CodeInterface,
    CodeMethod,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_logic_structures(
    db: AsyncSession,
    project_id: UUID,
) -> dict[str, Any] | None:
    """Return the latest completed ``logic_structures`` payload, or ``None``.

    Mirrors the E2 query in ``document_tasks`` (gap analysis / traceability):
    read ``AnalysisResult`` for the project with ``module == "logic_structures"``
    and ``status == COMPLETED``. ``None`` (no code analysis yet) is non-fatal —
    the caller then compares against an empty code structure.
    """
    result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.project_id == project_id,
            AnalysisResult.module == "logic_structures",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
    )
    ar = result.scalars().first()
    return ar.result_data if ar else None


def _map_method(raw: dict[str, Any]) -> CodeMethod | None:
    name = raw.get("name")
    if not name:
        return None
    parameters = raw.get("parameters") or []
    return CodeMethod(
        name=name,
        return_type=raw.get("return_type"),
        parameter_count=len(parameters),
    )


def _map_attribute(raw: dict[str, Any]) -> CodeAttribute | None:
    name = raw.get("name")
    if not name:
        return None
    return CodeAttribute(
        name=name,
        type=raw.get("type"),
        visibility=raw.get("visibility"),
    )


def _map_methods(raw_methods: list[dict[str, Any]] | None) -> list[CodeMethod]:
    methods: list[CodeMethod] = []
    for raw in raw_methods or []:
        mapped = _map_method(raw)
        if mapped is not None:
            methods.append(mapped)
    return methods


class LogicStructuresCodeProvider:
    """Supplies code structure from the project's ``logic_structures`` (Epic 1).

    Construct with the request DB session, then ``await load(project_id)`` to
    resolve the ``logic_structures`` payload before the synchronous
    ``ICodeStructureProvider`` getters are called by ``DiagramCodeComparator``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._payload: dict[str, Any] | None = None

    async def load(self, project_id: UUID) -> None:
        """Resolve and cache the ``logic_structures`` payload for the project."""
        self._payload = await fetch_logic_structures(self._db, project_id)

    def get_classes(self, project_id: UUID) -> list[CodeClass]:
        classes: list[CodeClass] = []
        for raw in (self._payload or {}).get("classes") or []:
            if raw.get("is_interface"):
                continue  # exposed via get_interfaces
            name = raw.get("name")
            if not name:
                continue
            attributes: list[CodeAttribute] = []
            for attr in raw.get("attributes") or []:
                mapped = _map_attribute(attr)
                if mapped is not None:
                    attributes.append(mapped)
            classes.append(
                CodeClass(
                    name=name,
                    attributes=attributes,
                    methods=_map_methods(raw.get("methods")),
                )
            )
        return classes

    def get_interfaces(self, project_id: UUID) -> list[CodeInterface]:
        interfaces: list[CodeInterface] = []
        for raw in (self._payload or {}).get("classes") or []:
            if not raw.get("is_interface"):
                continue
            name = raw.get("name")
            if not name:
                continue
            interfaces.append(
                CodeInterface(
                    name=name,
                    methods=_map_methods(raw.get("methods")),
                )
            )
        return interfaces
