from fastapi import APIRouter

from app.api.routes import (
    admin,
    admin_cve,
    analysis,
    api_keys,
    auth,
    billing,
    chat,
    codegen,
    dashboard,
    documents,
    gap_analysis,
    gherkin,
    gui,
    healing,
    health,
    integrations,
    integrations_scm,
    integrations_tms,
    jira_import,
    notifications,
    projects,
    report_exports,
    security_scan,
    sync,
    tasks,
    tenants,
    test_cases,
    traceability,
    uml,
    uploads,
    users,
    webhooks,
    webhooks_tpay,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(api_keys.router)
api_router.include_router(tenants.router)
api_router.include_router(projects.router)
api_router.include_router(uploads.router)
api_router.include_router(uml.router)
api_router.include_router(gui.router)
api_router.include_router(gherkin.router)
api_router.include_router(codegen.router)
api_router.include_router(healing.router)
api_router.include_router(documents.router)
api_router.include_router(gap_analysis.router)
api_router.include_router(analysis.router)
api_router.include_router(test_cases.router)
api_router.include_router(report_exports.router)
api_router.include_router(traceability.router)
api_router.include_router(security_scan.router)
api_router.include_router(integrations.router)
# Trasy TMS przed SCM: ``/integrations/testrail/...`` musi wygrać
# z ``/integrations/{integration_id}/config`` (Story 8.3), inaczej
# „testrail" byłoby parsowane jako UUID integracji.
api_router.include_router(integrations_tms.router)
api_router.include_router(integrations_tms.jira_router)
api_router.include_router(integrations_scm.router)
# Trasy synchronizacji po SCM: ``/integrations/{uuid}/sync/...`` nie koliduje
# z literałami TMS, ale kolejność trzyma całą rodzinę /integrations razem.
api_router.include_router(sync.router)
api_router.include_router(sync.conflicts_router)
api_router.include_router(jira_import.router)
api_router.include_router(admin_cve.router)
api_router.include_router(admin.router)
api_router.include_router(tasks.router)
api_router.include_router(dashboard.router)
api_router.include_router(chat.router)
api_router.include_router(billing.router)
api_router.include_router(notifications.router)
api_router.include_router(webhooks.router)
api_router.include_router(webhooks_tpay.router)
