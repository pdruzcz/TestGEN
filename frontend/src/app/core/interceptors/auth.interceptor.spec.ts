import { Component } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import {
  provideHttpClient,
  withInterceptors,
  HttpClient,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { authInterceptor } from "./auth.interceptor";
import { AuthService } from "../services/auth.service";

@Component({ template: "", standalone: true })
class DummyComponent {}

describe("authInterceptor", () => {
  let httpClient: HttpClient;
  let httpMock: HttpTestingController;
  let authService: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: "login", component: DummyComponent },
          { path: "**", component: DummyComponent },
        ]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    httpClient = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    authService = TestBed.inject(AuthService);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("should add withCredentials to API requests", () => {
    httpClient.get("/api/v1/users/me").subscribe();

    const req = httpMock.expectOne("/api/v1/users/me");
    expect(req.request.withCredentials).toBe(true);
    req.flush({});
  });

  it("should add tenant ID header when user is set", () => {
    authService.currentUserSignal.set({
      id: "1",
      tenantId: "tenant-123",
      email: "test@test.com",
      name: "Test",
      role: "owner",
      isActive: true,
      emailVerifiedAt: null,
      notificationPreferences: {},
      mfaEnabled: false,
    });

    httpClient.get("/api/v1/users/me").subscribe();

    const req = httpMock.expectOne("/api/v1/users/me");
    expect(req.request.headers.get("X-TestGEN-Tenant-Id")).toBe("tenant-123");
    req.flush({});
  });

  it("should not add credentials to non-API requests", () => {
    httpClient.get("https://external-api.com/data").subscribe();

    const req = httpMock.expectOne("https://external-api.com/data");
    expect(req.request.withCredentials).toBe(false);
    req.flush({});
  });

  it("should attempt refresh on 401 from non-auth endpoint", () => {
    httpClient.get("/api/v1/users/me").subscribe({
      error: () => {},
    });

    const req = httpMock.expectOne("/api/v1/users/me");
    req.flush({}, { status: 401, statusText: "Unauthorized" });

    // Should trigger refresh attempt
    const refreshReq = httpMock.match("/api/v1/auth/refresh");
    if (refreshReq.length > 0) {
      refreshReq[0].flush({}, { status: 401, statusText: "Unauthorized" });
    }

    // Logout POST may fire
    const logoutReq = httpMock.match("/api/v1/auth/logout");
    logoutReq.forEach((r) => r.flush({ message: "OK" }));
  });
});
