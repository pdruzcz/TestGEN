import { Routes } from "@angular/router";
import { authGuard } from "./core/guards/auth.guard";
import { roleGuard } from "./core/guards/role.guard";

export const routes: Routes = [
  {
    path: "login",
    title: "Logowanie — TestGEN",
    loadComponent: () =>
      import("./features/auth/login/login.component").then(
        (m) => m.LoginComponent,
      ),
  },
  {
    path: "register",
    title: "Rejestracja — TestGEN",
    loadComponent: () =>
      import("./features/auth/register/register.component").then(
        (m) => m.RegisterComponent,
      ),
  },
  {
    path: "verify-email",
    title: "Weryfikacja email — TestGEN",
    loadComponent: () =>
      import("./features/auth/email-verification/email-verification.component").then(
        (m) => m.EmailVerificationComponent,
      ),
  },
  {
    path: "set-password",
    title: "Ustaw hasło — TestGEN",
    loadComponent: () =>
      import("./features/auth/set-password/set-password.component").then(
        (m) => m.SetPasswordComponent,
      ),
  },
  {
    path: "reset-password",
    title: "Resetuj hasło — TestGEN",
    loadComponent: () =>
      import("./features/auth/reset-password/reset-password.component").then(
        (m) => m.ResetPasswordComponent,
      ),
  },
  {
    path: "mfa-verify",
    title: "Weryfikacja MFA — TestGEN",
    loadComponent: () =>
      import("./features/auth/mfa-verify/mfa-verify.component").then(
        (m) => m.MfaVerifyComponent,
      ),
  },
  {
    path: "select-tenant",
    title: "Wybór organizacji — TestGEN",
    loadComponent: () =>
      import("./features/auth/select-tenant/select-tenant.component").then(
        (m) => m.SelectTenantComponent,
      ),
  },
  {
    path: "settings/mfa",
    title: "Ustawienia MFA — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/settings/mfa-setup/mfa-setup.component").then(
        (m) => m.MfaSetupComponent,
      ),
  },
  {
    path: "settings/profile",
    title: "Profil — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/settings/profile/profile.component").then(
        (m) => m.ProfileComponent,
      ),
  },
  {
    path: "users/invite",
    title: "Zaproś użytkownika — TestGEN",
    canActivate: [authGuard, roleGuard("owner", "admin")],
    loadComponent: () =>
      import("./features/users/invite/invite.component").then(
        (m) => m.InviteComponent,
      ),
  },
  {
    path: "projects",
    title: "Projekty — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/projects.component").then(
        (m) => m.ProjectsComponent,
      ),
  },
  {
    path: "projects/:projectId/files",
    title: "Pliki projektu — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/project-files/project-files.component").then(
        (m) => m.ProjectFilesComponent,
      ),
  },
  {
    path: "projects/:projectId/preprocessing",
    title: "Preprocessing — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/preprocessing-report/preprocessing-report.component").then(
        (m) => m.PreprocessingReportComponent,
      ),
  },
  {
    path: "projects/:projectId/documents",
    title: "Dokumentacja projektu — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/document-upload/document-upload.component").then(
        (m) => m.DocumentUploadComponent,
      ),
  },
  {
    path: "projects/:projectId/documents/:documentId",
    title: "Podgląd dokumentu — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/document-view/document-view.component").then(
        (m) => m.DocumentViewComponent,
      ),
  },
  {
    path: "projects/:projectId/documents/:documentId/sections",
    title: "Sekcje dokumentu — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/doc-sections/doc-sections.component").then(
        (m) => m.DocSectionsComponent,
      ),
  },
  {
    path: "projects/:projectId/uml",
    title: "Diagramy UML — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/uml-upload/uml-upload.component").then(
        (m) => m.UmlUploadComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/flows",
    title: "User flows — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/flows-viewer/flows-viewer.component").then(
        (m) => m.FlowsViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/sequence/:diagramId",
    title: "Diagram sekwencji — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/sequence-viewer/sequence-viewer.component").then(
        (m) => m.SequenceViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/usecase/:diagramId",
    title: "Diagram przypadków użycia — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/usecase-viewer/usecase-viewer.component").then(
        (m) => m.UsecaseViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/class/:diagramId",
    title: "Diagram klas — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/class-viewer/class-viewer.component").then(
        (m) => m.ClassViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/activity/:diagramId",
    title: "Diagram aktywności — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/activity-viewer/activity-viewer.component").then(
        (m) => m.ActivityViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/uml/state/:diagramId",
    title: "Diagram stanów — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/uml/components/state-viewer/state-viewer.component").then(
        (m) => m.StateViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/gui",
    title: "Zrzuty ekranu GUI — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/gui/components/gui-upload/gui-upload.component").then(
        (m) => m.GuiUploadComponent,
      ),
  },
  {
    path: "projects/:projectId/gui/flows",
    title: "Przepływy użytkownika GUI — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/gui/components/gui-flow/gui-flow.component").then(
        (m) => m.GuiFlowComponent,
      ),
  },
  {
    path: "projects/:projectId/gui/compare",
    title: "Regresja wizualna GUI — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/gui/components/gui-comparison/gui-comparison.component").then(
        (m) => m.GuiComparisonComponent,
      ),
  },
  {
    path: "projects/:projectId/gui/:screenshotId/result",
    title: "Wynik analizy GUI — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/gui/components/gui-result/gui-result.component").then(
        (m) => m.GuiResultComponent,
      ),
  },
  {
    path: "projects/:projectId/gherkin",
    title: "Scenariusze Gherkin/BDD — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/gherkin/components/gherkin-generator/gherkin-generator.component").then(
        (m) => m.GherkinGeneratorComponent,
      ),
  },
  {
    path: "projects/:projectId/traceability-matrix",
    title: "Macierz śledzenia UML/GUI — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/traceability/components/traceability-matrix/traceability-matrix.component").then(
        (m) => m.TraceabilityMatrixComponent,
      ),
  },
  {
    path: "projects/:projectId/codegen/cypress",
    title: "Generator kodu Cypress — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/codegen/components/cypress-generator/cypress-generator.component").then(
        (m) => m.CypressGeneratorComponent,
      ),
  },
  {
    path: "projects/:projectId/codegen/database",
    title: "Generator kodu testów bazodanowych — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/codegen/components/database-generator/database-generator.component").then(
        (m) => m.DatabaseGeneratorComponent,
      ),
  },
  {
    path: "projects/:projectId/codegen/php",
    title: "Generator kodu testów PHP (PHPUnit/Pest) — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/codegen/components/php-generator/php-generator.component").then(
        (m) => m.PhpGeneratorComponent,
      ),
  },
  {
    path: "projects/:projectId/requirements",
    title: "Wymagania — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/requirements/requirement-list.component").then(
        (m) => m.RequirementListComponent,
      ),
  },
  {
    path: "projects/:projectId/glossary",
    title: "Glosariusz — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/glossary/glossary-list.component").then(
        (m) => m.GlossaryListComponent,
      ),
  },
  {
    path: "projects/:projectId/inconsistencies",
    title: "Niespójności — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/inconsistencies/inconsistency-viewer.component").then(
        (m) => m.InconsistencyViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/coverage-report",
    title: "Raport pokrycia — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/gap/gap-analysis-viewer.component").then(
        (m) => m.GapAnalysisViewerComponent,
      ),
  },
  {
    path: "projects/:projectId/gap-analysis",
    title: "Luki funkcjonalne — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/gap-analysis/gap-analysis.component").then(
        (m) => m.GapAnalysisComponent,
      ),
  },
  {
    path: "projects/:projectId/compliance",
    title: "Compliance — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/compliance/compliance.component").then(
        (m) => m.ComplianceComponent,
      ),
  },
  {
    path: "projects/:projectId/code-errors",
    title: "Błędy kodu — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/code-errors/code-errors.component").then(
        (m) => m.CodeErrorsComponent,
      ),
  },
  {
    path: "projects/:projectId/recommendations",
    title: "Rekomendacje — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/recommendations/recommendations.component").then(
        (m) => m.RecommendationsComponent,
      ),
  },
  {
    path: "projects/:projectId/comparison",
    title: "Porównanie wersji — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/comparison/comparison.component").then(
        (m) => m.ComparisonComponent,
      ),
  },
  {
    path: "projects/:projectId/integrations",
    title: "Integracje — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/integrations/integrations.component").then(
        (m) => m.IntegrationsComponent,
      ),
  },
  {
    path: "projects/:projectId/traceability",
    title: "Macierz traceability — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/analysis/traceability/traceability-matrix.component").then(
        (m) => m.TraceabilityMatrixComponent,
      ),
  },
  {
    path: "projects/:projectId/analysis",
    title: "Analiza — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/analysis/analysis.component").then(
        (m) => m.AnalysisComponent,
      ),
  },
  {
    path: "projects/:projectId/results",
    canActivate: [authGuard],
    loadChildren: () =>
      import("./features/results/results.routes").then((m) => m.RESULTS_ROUTES),
  },
  {
    path: "projects/:projectId/test-cases",
    title: "Przypadki testowe — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/test-cases/test-cases-management/test-cases-management.component").then(
        (m) => m.TestCasesManagementComponent,
      ),
  },
  {
    path: "projects/:projectId/test-cases/:testCaseId",
    title: "Przypadek testowy — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/test-cases/test-case-detail/test-case-detail.component").then(
        (m) => m.TestCaseDetailComponent,
      ),
  },
  {
    path: "projects/:projectId/security",
    title: "Skanowanie bezpieczeństwa — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/security/components/scan-launcher/scan-launcher.component").then(
        (m) => m.ScanLauncherComponent,
      ),
  },
  {
    path: "projects/:projectId/reports",
    title: "Raporty — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/reports/reports.component").then(
        (m) => m.ReportsComponent,
      ),
  },
  {
    path: "projects/:projectId/healing",
    title: "Self-healing — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/healing/healing.component").then(
        (m) => m.HealingComponent,
      ),
  },
  {
    path: "projects/:projectId",
    title: "Projekt — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/projects/project-detail/project-detail.component").then(
        (m) => m.ProjectDetailComponent,
      ),
  },
  {
    path: "settings/users",
    title: "Uzytkownicy — TestGEN",
    canActivate: [authGuard, roleGuard("owner", "admin")],
    loadComponent: () =>
      import("./features/settings/users/users.component").then(
        (m) => m.UsersComponent,
      ),
  },
  {
    path: "projects/:projectId/integrations/testrail",
    title: "Integracja TestRail — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import(
        "./features/integrations/testrail-config/testrail-config.component"
      ).then((m) => m.TestrailConfigComponent),
  },
  {
    path: "projects/:projectId/integrations/jira",
    title: "Integracja Jira — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/integrations/jira-config/jira-config.component").then(
        (m) => m.JiraConfigComponent,
      ),
  },
  {
    path: "projects/:projectId/import/jira",
    title: "Import z Jiry — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/integrations/jira-import/jira-import.component").then(
        (m) => m.JiraImportComponent,
      ),
  },
  {
    path: "projects/:projectId/ci-cd",
    title: "Konfiguracja CI/CD — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/integrations/cicd-config/cicd-config.component").then(
        (m) => m.CicdConfigComponent,
      ),
  },
  {
    path: "settings/integrations",
    canActivate: [authGuard, roleGuard("owner", "admin")],
    loadChildren: () =>
      import("./features/integrations/integrations.routes").then(
        (m) => m.INTEGRATIONS_ROUTES,
      ),
  },
  {
    path: "settings/api-keys",
    title: "Klucze API — TestGEN",
    canActivate: [authGuard, roleGuard("owner", "admin")],
    loadComponent: () =>
      import("./features/settings/api-keys/api-keys.component").then(
        (m) => m.ApiKeysComponent,
      ),
  },
  {
    path: "billing",
    canActivate: [authGuard, roleGuard("owner")],
    loadChildren: () =>
      import("./features/billing/billing.routes").then((m) => m.BILLING_ROUTES),
  },
  {
    path: "admin/cve-pipeline",
    title: "Pipeline CVE — TestGEN",
    canActivate: [authGuard, roleGuard("admin")],
    loadComponent: () =>
      import("./features/admin/cve-pipeline/cve-pipeline.component").then(
        (m) => m.CvePipelineComponent,
      ),
  },
  {
    path: "admin",
    canActivate: [authGuard, roleGuard("admin")],
    loadChildren: () =>
      import("./features/admin/admin.routes").then((m) => m.ADMIN_ROUTES),
  },
  {
    path: "403",
    title: "Brak dostępu — TestGEN",
    loadComponent: () =>
      import("./features/errors/forbidden/forbidden.component").then(
        (m) => m.ForbiddenComponent,
      ),
  },
  {
    path: "dashboard",
    title: "Dashboard — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/dashboard/dashboard.component").then(
        (m) => m.DashboardComponent,
      ),
  },
  {
    path: "upload-demo",
    title: "Upload demo — TestGEN",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/upload-demo/upload-demo.component").then(
        (m) => m.UploadDemoComponent,
      ),
  },
  { path: "", redirectTo: "dashboard", pathMatch: "full" },
  {
    path: "**",
    title: "Nie znaleziono — TestGEN",
    loadComponent: () =>
      import("./features/errors/not-found/not-found.component").then(
        (m) => m.NotFoundComponent,
      ),
  },
];
