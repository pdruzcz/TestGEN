import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";

import { environment } from "../../../../../environments/environment";
import { AdminAuditLogEntry } from "../../services/admin.service";
import { AuditLogComponent } from "./audit-log.component";

const API = environment.apiUrl;

const ENTRY: AdminAuditLogEntry = {
  id: "a1",
  createdAt: "2026-07-20T10:00:00Z",
  tenantId: "t1",
  userId: "u1",
  action: "user.blocked",
  resourceType: "user",
  resourceId: "u2",
  details: { oldBlocked: false },
  ipAddress: "10.0.0.1",
};

describe("AuditLogComponent", () => {
  let fixture: ComponentFixture<AuditLogComponent>;
  let component: AuditLogComponent;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [AuditLogComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
      ],
    });
    fixture = TestBed.createComponent(AuditLogComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  function initialLoad(logs: AdminAuditLogEntry[] = [ENTRY]): void {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/audit-logs`)
      .flush({ logs, total: logs.length });
    httpTesting
      .expectOne(`${API}/admin/audit-logs/actions`)
      .flush(["user.blocked", "platform.config_updated"]);
    fixture.detectChanges();
  }

  it("pobiera wpisy i listę akcji przy inicjalizacji", () => {
    initialLoad();

    expect(component.logs().length).toBe(1);
    expect(component.actions().length).toBe(2);
  });

  it("wyświetla kolumny wymagane przez story", () => {
    initialLoad();

    expect(component.displayedColumns).toEqual([
      "createdAt",
      "userId",
      "action",
      "resource",
      "details",
      "ipAddress",
    ]);
  });

  it("renderuje wpis logu", () => {
    initialLoad();
    const text: string = fixture.nativeElement.textContent;

    expect(text).toContain("user.blocked");
    expect(text).toContain("10.0.0.1");
  });

  it("serializuje szczegóły wpisu do postaci tekstowej", () => {
    expect(component.formatDetails(ENTRY.details)).toContain("oldBlocked");
    expect(component.formatDetails(null)).toBe("—");
  });

  it("stosuje filtry daty, użytkownika i akcji", () => {
    initialLoad();

    component.filters.patchValue({
      dateFrom: new Date("2026-01-01T00:00:00Z"),
      dateTo: new Date("2026-02-01T00:00:00Z"),
      userId: "u1",
      action: "user.blocked",
    });
    component.applyFilters();

    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/audit-logs`);
    expect(req.request.params.get("user_id")).toBe("u1");
    expect(req.request.params.get("action")).toBe("user.blocked");
    expect(req.request.params.get("date_from")).toContain("2026-01-01");
    req.flush({ logs: [], total: 0 });
  });

  it("pomija puste filtry", () => {
    initialLoad();

    component.applyFilters();

    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/audit-logs`);
    expect(req.request.params.has("action")).toBe(false);
    expect(req.request.params.has("user_id")).toBe(false);
    req.flush({ logs: [], total: 0 });
  });

  it("czyszczenie filtrów przywraca pełną listę", () => {
    initialLoad();

    component.filters.patchValue({ action: "user.blocked" });
    component.clearFilters();

    expect(component.filters.value.action).toBe("");
    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/audit-logs`);
    expect(req.request.params.has("action")).toBe(false);
    req.flush({ logs: [ENTRY], total: 1 });
  });

  it("zmiana strony odpytuje backend z nową paginacją", () => {
    initialLoad();

    component.onPageChange({ pageIndex: 2, pageSize: 50, length: 300 });
    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/audit-logs`);

    expect(req.request.params.get("page")).toBe("3");
    expect(req.request.params.get("page_size")).toBe("50");
    req.flush({ logs: [], total: 300 });
  });

  it("pokazuje komunikat błędu przy nieudanym pobraniu", () => {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/audit-logs`)
      .flush(null, { status: 500, statusText: "Server Error" });
    httpTesting.expectOne(`${API}/admin/audit-logs/actions`).flush([]);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain("logu audytu");
  });
});
