import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../../environments/environment";
import { AdminTenant } from "../../services/admin.service";
import { TenantManagementComponent } from "./tenant-management.component";

const API = environment.apiUrl;

const TENANT: AdminTenant = {
  id: "t1",
  name: "Acme",
  slug: "acme",
  plan: "premium",
  isActive: true,
  createdAt: "2026-01-01T00:00:00Z",
  userCount: 5,
  storageBytes: 2 * 1024 * 1024,
  projectCount: 2,
};

describe("TenantManagementComponent", () => {
  let fixture: ComponentFixture<TenantManagementComponent>;
  let component: TenantManagementComponent;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [TenantManagementComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
      ],
    });
    fixture = TestBed.createComponent(TenantManagementComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  function initialLoad(tenants: AdminTenant[] = [TENANT]): void {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush({ tenants, total: tenants.length });
    fixture.detectChanges();
  }

  it("pobiera tenantów przy inicjalizacji", () => {
    initialLoad();

    expect(component.tenants().length).toBe(1);
    expect(component.total()).toBe(1);
  });

  it("wyświetla kolumny wymagane przez story", () => {
    initialLoad();

    expect(component.displayedColumns).toEqual([
      "name",
      "plan",
      "userCount",
      "storage",
      "projectCount",
      "status",
      "createdAt",
    ]);
  });

  it("renderuje wiersz tenanta", () => {
    initialLoad();

    expect(fixture.nativeElement.textContent).toContain("Acme");
  });

  it("formatuje zajętość storage w jednostkach czytelnych dla człowieka", () => {
    expect(component.formatStorage(0)).toBe("0 B");
    expect(component.formatStorage(2048)).toBe("2 KB");
    expect(component.formatStorage(2 * 1024 * 1024)).toBe("2 MB");
    expect(component.formatStorage(3 * 1024 * 1024 * 1024)).toBe("3 GB");
  });

  it("opisuje status tenanta po polsku", () => {
    expect(component.statusLabel(TENANT)).toBe("Aktywny");
    expect(component.statusLabel({ ...TENANT, isActive: false })).toBe(
      "Nieaktywny",
    );
  });

  it("wyszukiwanie odpytuje backend z frazą", () => {
    initialLoad();

    component.searchControl.setValue("acme");
    component.applySearch();
    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/tenants`);

    expect(req.request.params.get("search")).toBe("acme");
    req.flush({ tenants: [], total: 0 });
  });

  it("wybór tenanta pobiera jego szczegóły i projekty", () => {
    initialLoad();

    component.selectTenant("t1");

    httpTesting.expectOne(`${API}/admin/tenants/t1`).flush(TENANT);
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants/t1/projects`)
      .flush({
        projects: [
          {
            id: "p1",
            name: "API",
            status: "active",
            createdAt: "2026-01-02T00:00:00Z",
          },
        ],
        total: 1,
      });
    fixture.detectChanges();

    expect(component.selectedTenant()?.name).toBe("Acme");
    expect(component.projects().length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain("API");
  });

  it("zmiana strony odpytuje backend z nową paginacją", () => {
    initialLoad();

    component.onPageChange({ pageIndex: 1, pageSize: 25, length: 40 });
    const req = httpTesting.expectOne((r) => r.url === `${API}/admin/tenants`);

    expect(req.request.params.get("page")).toBe("2");
    req.flush({ tenants: [], total: 40 });
  });

  it("pokazuje komunikat błędu przy nieudanym pobraniu", () => {
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/admin/tenants`)
      .flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain("tenantów");
  });
});
