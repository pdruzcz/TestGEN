"""Native remediation templates — Epic 4, Story 4.9.

Importing this package registers every template module in the shared registry so
``TemplateRegistry`` can resolve them. Templates are keyed by
(vulnerability_type, language, framework) with graceful degradation.
"""

from app.services.security_scan.recommendation_templates import (
    authz_templates,
    csrf_templates,
    input_validation_templates,
    secrets_templates,
    sqli_templates,
    xss_templates,
)
from app.services.security_scan.recommendation_templates.registry import (
    Template,
    TemplateRegistry,
    register,
)

__all__ = [
    "Template",
    "TemplateRegistry",
    "authz_templates",
    "csrf_templates",
    "input_validation_templates",
    "register",
    "secrets_templates",
    "sqli_templates",
    "xss_templates",
]
