import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it } from "vitest";

import { environment } from "../../../environments/environment";
import { ModuleLocksService } from "./module-locks.service";

/** Story 7.13 — signal moduleLocks z GET /billing/features. */
describe("ModuleLocksService (Story 7.13)", () => {
  let service: ModuleLocksService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ModuleLocksService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function flush(status: { currentPlan: string; modules: unknown[] }): void {
    service.refresh();
    const req = httpMock.expectOne(`${environment.apiUrl}/billing/features`);
    expect(req.request.method).toBe("GET");
    req.flush(status);
  }

  it("mapuje moduły na blokady po refresh (freemium — progi basic/premium)", () => {
    flush({
      currentPlan: "freemium",
      modules: [
        { key: "security", locked: true, requiredPlan: "premium" },
        { key: "uml", locked: true, requiredPlan: "basic" },
        { key: "code_analysis", locked: false, requiredPlan: null },
      ],
    });

    expect(service.currentPlan()).toBe("freemium");
    expect(service.isLocked("security")).toBe(true);
    expect(service.isLocked("uml")).toBe(true);
    expect(service.isLocked("code_analysis")).toBe(false);
    expect(service.requiredPlanOf("security")).toBe("premium");
  });

  it("reaktywny unlock — drugi refresh nadpisuje blokady po upgrade", () => {
    flush({
      currentPlan: "freemium",
      modules: [{ key: "uml", locked: true, requiredPlan: "basic" }],
    });
    expect(service.isLocked("uml")).toBe(true);

    flush({
      currentPlan: "premium",
      modules: [{ key: "uml", locked: false, requiredPlan: null }],
    });
    expect(service.isLocked("uml")).toBe(false);
    expect(service.currentPlan()).toBe("premium");
  });

  it("fail-open — błąd API nie blokuje modułów (egzekwuje backend, 402)", () => {
    service.refresh();
    const req = httpMock.expectOne(`${environment.apiUrl}/billing/features`);
    req.flush("error", { status: 500, statusText: "Server Error" });

    expect(service.isLocked("security")).toBe(false);
    expect(service.currentPlan()).toBeNull();
  });

  it("nieznany moduł → niezablokowany (fail-open)", () => {
    flush({ currentPlan: "freemium", modules: [] });
    expect(service.isLocked("does_not_exist")).toBe(false);
    expect(service.requiredPlanOf("does_not_exist")).toBeNull();
  });
});
