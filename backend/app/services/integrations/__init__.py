"""Integracje zewnętrzne.

Trackery (Epic 5): ``jira_service``, ``azure_devops_service``.
Hosting kodu (Epic 8): ``github_service`` + wspólne przyjmowanie zdarzeń
w ``scm_webhook_service``.

Moduły importujemy leniwie w miejscu użycia — ``jira_service`` i
``azure_devops_service`` ciągną klientów HTTP, których nie chcemy ładować
przy każdym starcie workera.
"""
