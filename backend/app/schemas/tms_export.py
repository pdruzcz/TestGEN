"""Schematy eksportu test case'ów do TMS — Story 6.8 (FR46)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

TmsFormat = Literal["testrail", "xray", "json"]


class TmsExportRequest(BaseModel):
    """Żądanie eksportu test case'ów do formatu TMS.

    Puste `ids` oznacza eksport wszystkich test case'ów tenanta (AC6 —
    frontend przekazuje IDs zaznaczonych lub przefiltrowanych rekordów).
    """

    format: TmsFormat
    ids: list[uuid.UUID] = Field(default_factory=list)
    project_id: uuid.UUID | None = None
    field_mapping: dict[str, str] | None = None
