"""Safe PoC payload library — Epic 4, Story 4.10.

Importing this package registers every payload module so ``PayloadRegistry`` can
resolve canonical, non-destructive demonstrations per vulnerability type.
"""

from app.services.security_scan.poc_payloads import (
    command_injection_payloads,
    path_traversal_payloads,
    sqli_payloads,
    xss_payloads,
)
from app.services.security_scan.poc_payloads.registry import (
    PayloadRegistry,
    PayloadTemplate,
    register,
)

__all__ = [
    "PayloadRegistry",
    "PayloadTemplate",
    "command_injection_payloads",
    "path_traversal_payloads",
    "register",
    "sqli_payloads",
    "xss_payloads",
]
