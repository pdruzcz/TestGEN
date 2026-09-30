import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../environments/environment";
import {
  blockingViolations,
  formatViolations,
  runAxe,
} from "../../shared/utils/axe-setup";
import { AdminComponent } from "./admin.component";
import { AuditLogComponent } from "./components/audit-log/audit-log.component";
import { PlatformConfigComponent } from "./components/platform-config/platform-config.component";
import { TenantManagementComponent } from "./components/tenant-management/tenant-management.component";
import { UserManagementComponent } from "./components/user-management/user-management.component";

const API = environment.apiUrl;

/** Story 6.15, AC8 — panel administracyjny bez naruszeń WCAG 2.1 AA. */
describe("Panel administracyjny — dostępność (WCAG 2.1 AA)", () => {
  // axe.run() na tabelarycznym DOM w jsdom jest CPU-żerny — pod pełnym
  // suite'em (równoległe workery) pierwsza sesja potrafi przekroczyć
  // globalny testTimeout 15 s, a niedomknięty run kaskaduje na kolejne
  // testy ("Axe is already running"). Stąd podwyższony limit per-test
  // (trzeci argument it — vi.setTestTimeout nie istnieje w tej wersji Vitest).
  const AXE_TEST_TIMEOUT = 60_000;
  const itAxe = (name: string, fn: () => Promise<void>) =>
    it(name, fn, AXE_TEST_TIMEOUT);

  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
      ],
    });
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  async function expectNoViolations(element: Element): Promise<void> {
    const violations = blockingViolations(await runAxe(element));
    expect(formatViolations(violations)).toBe(
      "Brak naruszeń dostępności (WCAG 2.1 AA).",
    );
  }

  itAxe("powłoka panelu nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(AdminComponent);
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("lista użytkowników nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(UserManagementComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/users`)
      .flush({
        users: [
          {
            id: "u1",
            tenantId: "t1",
            email: "jan@example.com",
            name: "Jan Kowalski",
            role: "user",
            isActive: true,
            isBlocked: false,
            deletedAt: null,
            createdAt: "2026-01-10T08:00:00Z",
            lastLoginAt: null,
          },
        ],
        total: 1,
      });
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush({ tenants: [], total: 0 });
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("lista tenantów nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(TenantManagementComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush({ tenants: [], total: 0 });
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("log audytu nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(AuditLogComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/audit-logs`)
      .flush({ logs: [], total: 0 });
    httpTesting.expectOne(`${API}/admin/audit-logs/actions`).flush([]);
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("konfiguracja platformy nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(PlatformConfigComponent);
    fixture.detectChanges();
    httpTesting.expectOne(`${API}/admin/config`).flush({
      limits: {
        maxFileSizeMb: 100,
        maxProjectsPerTenant: 50,
        maxUsersPerTenant: 25,
        llmCostLimitUsd: 100,
      },
      llm: {
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        temperature: 0.2,
        maxTokens: 4096,
        timeoutSeconds: 60,
      },
      maintenance: { enabled: false, message: "" },
      featureFlags: { aiAssistant: true },
    });
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });
});
