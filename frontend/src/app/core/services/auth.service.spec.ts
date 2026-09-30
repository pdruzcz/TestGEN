import { Component } from "@angular/core";
import { TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { AuthService, LoginResponse, UserProfile } from "./auth.service";
import { environment } from "../../../environments/environment";

@Component({ template: "", standalone: true })
class DummyComponent {}

describe("AuthService", () => {
  let service: AuthService;
  let httpTesting: HttpTestingController;
  const apiUrl = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideRouter([
          { path: "login", component: DummyComponent },
          { path: "**", component: DummyComponent },
        ]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(AuthService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  describe("signals", () => {
    it("should start with null currentUserSignal", () => {
      expect(service.currentUserSignal()).toBeNull();
    });

    it("should start with isAuthenticated false", () => {
      expect(service.isAuthenticatedSignal()).toBe(false);
    });

    it("should start with isLoading false", () => {
      expect(service.isLoadingSignal()).toBe(false);
    });
  });

  describe("register", () => {
    it("should POST to /auth/register", () => {
      const payload = {
        email: "test@test.com",
        password: "StrongPass123!",
        companyName: "Test Corp",
      };
      service.register(payload).subscribe((res) => {
        expect(res.message).toBe("Check email");
      });

      const req = httpTesting.expectOne(`${apiUrl}/auth/register`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual(payload);
      req.flush({ email: "test@test.com", message: "Check email" });
    });

    it("should include nip when provided", () => {
      const payload = {
        email: "test@test.com",
        password: "StrongPass123!",
        companyName: "Test Corp",
        nip: "1234567890",
      };
      service.register(payload).subscribe();
      const req = httpTesting.expectOne(`${apiUrl}/auth/register`);
      expect(req.request.body.nip).toBe("1234567890");
      req.flush({ email: "test@test.com", message: "ok" });
    });
  });

  describe("login", () => {
    it("should POST to /auth/login", () => {
      const response: LoginResponse = {
        message: "Login successful",
        mfaRequired: false,
        mfaToken: null,
        tenantsRequired: false,
        preAuthToken: null,
        tenants: null,
      };

      service.login("test@test.com", "password").subscribe((res) => {
        expect(res.mfaRequired).toBe(false);
      });

      const req = httpTesting.expectOne(`${apiUrl}/auth/login`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        email: "test@test.com",
        password: "password",
      });
      req.flush(response);
    });

    it("should return mfaRequired when MFA is needed", () => {
      const response: LoginResponse = {
        message: "MFA verification required",
        mfaRequired: true,
        mfaToken: "mfa-jwt-token",
        tenantsRequired: false,
        preAuthToken: null,
        tenants: null,
      };

      service.login("mfa@test.com", "password").subscribe((res) => {
        expect(res.mfaRequired).toBe(true);
        expect(res.mfaToken).toBe("mfa-jwt-token");
      });

      const req = httpTesting.expectOne(`${apiUrl}/auth/login`);
      req.flush(response);
    });
  });

  describe("verifyMfa", () => {
    it("should POST to /auth/mfa/verify", () => {
      service.verifyMfa("mfa-token", "123456").subscribe();

      const req = httpTesting.expectOne(`${apiUrl}/auth/mfa/verify`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        mfaToken: "mfa-token",
        code: "123456",
      });
      req.flush({ message: "OK", mfaRequired: false, mfaToken: null });
    });
  });

  describe("verifyEmail", () => {
    it("should POST token in body", () => {
      service.verifyEmail("abc123").subscribe((res) => {
        expect(res.message).toBe("Verified");
      });
      const req = httpTesting.expectOne(`${apiUrl}/auth/verify-email`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({ token: "abc123" });
      req.flush({ message: "Verified" });
    });
  });

  describe("acceptInvitation", () => {
    it("should POST token and password", () => {
      service.acceptInvitation("tok123", "NewPassword123!").subscribe((res) => {
        expect(res.message).toBe("Accepted");
      });
      const req = httpTesting.expectOne(`${apiUrl}/auth/accept-invitation`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        token: "tok123",
        password: "NewPassword123!",
      });
      req.flush({ message: "Accepted" });
    });
  });

  describe("resetPasswordByToken", () => {
    it("should POST token and newPassword", () => {
      service
        .resetPasswordByToken("tok456", "ResetPass123!")
        .subscribe((res) => {
          expect(res.message).toBe("Reset");
        });
      const req = httpTesting.expectOne(`${apiUrl}/users/reset-password-token`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        token: "tok456",
        newPassword: "ResetPass123!",
      });
      req.flush({ message: "Reset" });
    });
  });

  describe("refreshToken", () => {
    it("should POST to /auth/refresh", () => {
      service.refreshToken().subscribe();

      const req = httpTesting.expectOne(`${apiUrl}/auth/refresh`);
      expect(req.request.method).toBe("POST");
      req.flush({ message: "Token refreshed" });
    });
  });

  describe("fetchProfile", () => {
    const mockProfile: UserProfile = {
      id: "uuid-1",
      tenantId: "tid-1",
      email: "me@test.com",
      name: "Test User",
      role: "owner",
      isActive: true,
      emailVerifiedAt: "2026-01-01T00:00:00Z",
      notificationPreferences: {},
      mfaEnabled: false,
    };

    it("should GET /users/me and update signal", () => {
      service.fetchProfile().subscribe((user) => {
        expect(user.email).toBe("me@test.com");
      });

      const req = httpTesting.expectOne(`${apiUrl}/users/me`);
      expect(req.request.method).toBe("GET");
      req.flush(mockProfile);

      expect(service.currentUserSignal()?.email).toBe("me@test.com");
      expect(service.isAuthenticatedSignal()).toBe(true);
    });

    it("should deduplicate concurrent fetchProfile calls", () => {
      service.fetchProfile().subscribe();
      service.fetchProfile().subscribe();

      const reqs = httpTesting.match(`${apiUrl}/users/me`);
      expect(reqs.length).toBe(1);
      reqs[0].flush(mockProfile);
    });

    it("should set isLoading during fetch", () => {
      expect(service.isLoadingSignal()).toBe(false);
      service.fetchProfile().subscribe();

      expect(service.isLoadingSignal()).toBe(true);

      const req = httpTesting.expectOne(`${apiUrl}/users/me`);
      req.flush(mockProfile);

      expect(service.isLoadingSignal()).toBe(false);
    });
  });

  describe("logout", () => {
    it("should clear currentUserSignal and POST to /auth/logout", () => {
      service.currentUserSignal.set({
        id: "1",
        tenantId: "t1",
        email: "a@b.com",
        name: "A",
        role: "user",
        isActive: true,
        emailVerifiedAt: null,
        notificationPreferences: {},
        mfaEnabled: false,
      });
      expect(service.isAuthenticatedSignal()).toBe(true);
      service.logout();
      expect(service.currentUserSignal()).toBeNull();
      expect(service.isAuthenticatedSignal()).toBe(false);

      // Flush the logout POST request
      const req = httpTesting.expectOne(`${apiUrl}/auth/logout`);
      expect(req.request.method).toBe("POST");
      req.flush({ message: "OK" });
    });
  });

  describe("MFA setup", () => {
    it("should POST to /auth/mfa/setup", () => {
      service.setupMfa().subscribe((res) => {
        expect(res.secret).toBe("ABCDEF");
      });

      const req = httpTesting.expectOne(`${apiUrl}/auth/mfa/setup`);
      expect(req.request.method).toBe("POST");
      req.flush({ secret: "ABCDEF", provisioningUri: "otpauth://..." });
    });

    it("should POST to /auth/mfa/confirm", () => {
      service.confirmMfa("123456").subscribe((res) => {
        expect(res.backupCodes.length).toBe(2);
      });

      const req = httpTesting.expectOne(`${apiUrl}/auth/mfa/confirm`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({ code: "123456" });
      req.flush({ backupCodes: ["a", "b"], message: "OK" });
    });

    it("should DELETE /auth/mfa", () => {
      service.disableMfa("password123").subscribe();

      const req = httpTesting.expectOne(`${apiUrl}/auth/mfa`);
      expect(req.request.method).toBe("DELETE");
      req.flush({ message: "MFA disabled" });
    });
  });

  describe("error handling", () => {
    it("should propagate HTTP errors on register", () => {
      let error: any;
      service
        .register({
          email: "a@b.com",
          password: "StrongPass123!",
          companyName: "X",
        })
        .subscribe({
          error: (err) => (error = err),
        });
      const req = httpTesting.expectOne(`${apiUrl}/auth/register`);
      req.flush(
        { detail: "Email already registered" },
        { status: 409, statusText: "Conflict" },
      );
      expect(error.status).toBe(409);
    });
  });
});
