import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { describe, expect, it, vi } from "vitest";

import { environment } from "../../../environments/environment";

import {
  FeatureLockAlertService,
  featureLockInterceptor,
} from "./feature-lock-interceptor";
import { ModuleLocksService } from "../../core/services/module-locks.service";

/** Story 7.13 — 402 feature_requires_plan → alert + refresh blokad. */
describe("featureLockInterceptor (Story 7.13)", () => {
  let client: HttpClient;
  let httpMock: HttpTestingController;
  let alerts: FeatureLockAlertService;
  let moduleLocks: ModuleLocksService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([featureLockInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    alerts = TestBed.inject(FeatureLockAlertService);
    moduleLocks = TestBed.inject(ModuleLocksService);
    // Refresh blokad wywołuje GET /billing/features — w teście interceptora
    // wystarczy fakt wywołania (assert poniżej), nie realne żądanie.
    vi.spyOn(moduleLocks, "refresh").mockImplementation(() => undefined);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("402 feature_requires_plan publikuje alert z wymaganym planem", async () => {
    const promise = client
      .post(`${environment.apiUrl}/projects/x/security-scan`, {})
      .toPromise()
      .catch((err) => err);

    httpMock.expectOne(`${environment.apiUrl}/projects/x/security-scan`).flush(
      {
        error: "feature_requires_plan",
        feature: "security",
        required_plan: "premium",
        upgrade_url: "/billing/plans",
      },
      { status: 402, statusText: "Payment Required" },
    );

    await promise;
    const alert = alerts.alert();
    expect(alert).not.toBeNull();
    expect(alert?.feature).toBe("security");
    expect(alert?.requiredPlan).toBe("premium");
  });

  it("402 feature_requires_plan odświeża blokady modułów", async () => {
    const promise = client
      .post(`${environment.apiUrl}/projects/x/uml/analyze`, {})
      .toPromise()
      .catch((err) => err);

    httpMock
      .expectOne(`${environment.apiUrl}/projects/x/uml/analyze`)
      .flush(
        {
          error: "feature_requires_plan",
          feature: "uml",
          required_plan: "basic",
        },
        { status: 402, statusText: "Payment Required" },
      );

    await promise;
    expect(moduleLocks.refresh).toHaveBeenCalled();
  });

  it("inny błąd 402 (bez feature_requires_plan) nie publikuje alertu", async () => {
    const promise = client
      .post(`${environment.apiUrl}/projects/x/other`, {})
      .toPromise()
      .catch((err) => err);

    httpMock
      .expectOne(`${environment.apiUrl}/projects/x/other`)
      .flush(
        { error: "other" },
        { status: 402, statusText: "Payment Required" },
      );

    await promise;
    expect(alerts.alert()).toBeNull();
  });
});
