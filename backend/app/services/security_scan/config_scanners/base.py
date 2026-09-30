"""Shared types for infrastructure-config scanners — Epic 4, Story 4.5.

``ConfigFinding`` is the per-rule result emitted by each scanner; ``IConfigScanner``
is the protocol every technology scanner (Docker / Kubernetes / Terraform)
implements so the orchestrator can route uniformly.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ConfigFinding:
    rule_id: str
    config_type: str  # docker / kubernetes / terraform
    severity: str  # critical / high / medium / low / info
    description: str
    recommendation: str
    fix_example: str = ""
    file_path: str | None = None
    line: int | None = None
    vulnerability_type: str = "misconfiguration"
    cwe_id: str | None = None
    source: str = "native"
    extra: dict = field(default_factory=dict)


class IConfigScanner(Protocol):
    """A technology-specific configuration scanner."""

    config_type: str

    def scan(self, content: str, filename: str) -> list[ConfigFinding]:
        ...
