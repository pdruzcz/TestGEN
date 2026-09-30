import { TestBed } from "@angular/core/testing";
import { HttpClient, provideHttpClient, withInterceptors } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { QuotaAlertService, quotaInterceptor } from "./quota-interceptor";

describe("quotaInterceptor (Story 7.8, AC6)", () => {
  let httpClient: HttpClient;
  let httpMock: HttpTestingController;
  let alerts: QuotaAlertService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([quotaInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    httpClient = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    alerts = TestBed.inject(QuotaAlertService);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("publikuje alert po 429 limit_reached (body AC1)", () => {
    httpClient.post("/api/v1/projects/x/analyze", {}).subscribe({ error: () => {} });

    httpMock.expectOne("/api/v1/projects/x/analyze").flush(
      {
        error: "limit_reached",
        resource: "analyses",
        limit: 10,
        current: 10,
        plan: "freemium",
      },
      { status: 429, statusText: "Too Many Requests" },
    );

    expect(alerts.alert()).toEqual({
      resource: "analyses",
      limit: 10,
      current: 10,
      plan: "freemium",
    });
  });

  it("przepuszcza błąd dalej (rethrow) po obsłużeniu 429", () => {
    let caughtStatus = 0;
    httpClient.get("/api/v1/billing/usage").subscribe({
      error: (err) => (caughtStatus = err.status),
    });

    httpMock.expectOne("/api/v1/billing/usage").flush(
      { error: "limit_reached", resource: "storage_bytes", limit: 1, current: 1, plan: "basic" },
      { status: 429, statusText: "Too Many Requests" },
    );

    expect(caughtStatus).toBe(429);
  });

  it("ignoruje 429 rate_limit_exceeded (middleware, nie quota)", () => {
    httpClient.get("/api/v1/projects").subscribe({ error: () => {} });

    httpMock.expectOne("/api/v1/projects").flush(
      { error: "rate_limit_exceeded", plan: "basic", limit: 100 },
      { status: 429, statusText: "Too Many Requests" },
    );

    expect(alerts.alert()).toBeNull();
  });

  it("ignoruje inne błędy (500)", () => {
    httpClient.get("/api/v1/projects").subscribe({ error: () => {} });

    httpMock
      .expectOne("/api/v1/projects")
      .flush({ detail: "boom" }, { status: 500, statusText: "Server Error" });

    expect(alerts.alert()).toBeNull();
  });

  it("dismiss czyści alert", () => {
    alerts.show({ resource: "analyses", limit: 10, current: 10, plan: "freemium" });
    alerts.dismiss();
    expect(alerts.alert()).toBeNull();
  });
});
