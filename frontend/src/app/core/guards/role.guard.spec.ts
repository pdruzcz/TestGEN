import { TestBed } from "@angular/core/testing";
import {
  Router,
  UrlTree,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
} from "@angular/router";
import { provideRouter } from "@angular/router";
import { roleGuard } from "./role.guard";
import { AuthService, UserProfile } from "../services/auth.service";
import { of, throwError, tap } from "rxjs";
import { signal } from "@angular/core";

describe("roleGuard", () => {
  let router: Router;

  const dummyRoute = {} as ActivatedRouteSnapshot;
  const dummyState = {} as RouterStateSnapshot;

  const mockUser: UserProfile = {
    id: "u1",
    tenantId: "t1",
    email: "admin@example.com",
    name: "Admin",
    role: "admin",
    isActive: true,
    emailVerifiedAt: "2026-01-01T00:00:00Z",
    notificationPreferences: {},
    mfaEnabled: false,
  };

  function createAuthService(user: UserProfile | null) {
    return {
      currentUserSignal: signal<UserProfile | null>(user),
      fetchProfile: vi.fn(),
    };
  }

  async function runGuard(
    mock: ReturnType<typeof createAuthService>,
    ...roles: string[]
  ): Promise<boolean | UrlTree> {
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: mock }],
    }).compileComponents();
    router = TestBed.inject(Router);
    const guard = roleGuard(...roles);
    return TestBed.runInInjectionContext(() =>
      guard(dummyRoute, dummyState),
    ) as Promise<boolean | UrlTree>;
  }

  it("should allow navigation when user has required role", async () => {
    const mock = createAuthService(mockUser);
    const result = await runGuard(mock, "admin", "owner");
    expect(result).toBe(true);
  });

  it("should redirect to /403 when user has wrong role", async () => {
    const userAsMember = { ...mockUser, role: "user" };
    const mock = createAuthService(userAsMember);
    const result = await runGuard(mock, "admin", "owner");
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe("/403");
  });

  it("should redirect to /login when user is null and fetchProfile fails", async () => {
    const mock = createAuthService(null);
    mock.fetchProfile.mockReturnValue(
      throwError(() => new Error("Unauthorized")),
    );
    const result = await runGuard(mock, "admin");
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe("/login");
  });

  it("should fetch profile for session restore when user is null", async () => {
    const mock = createAuthService(null);
    mock.fetchProfile.mockReturnValue(
      of(mockUser).pipe(tap(() => mock.currentUserSignal.set(mockUser))),
    );
    const result = await runGuard(mock, "admin");
    expect(mock.fetchProfile).toHaveBeenCalled();
    expect(result).toBe(true);
  });

  it("should redirect to /login when user signal stays null after fetchProfile", async () => {
    const mock = createAuthService(null);
    mock.fetchProfile.mockReturnValue(of(null));
    const result = await runGuard(mock, "admin");
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe("/login");
  });

  it("should allow single role check", async () => {
    const ownerUser = { ...mockUser, role: "owner" };
    const mock = createAuthService(ownerUser);
    const result = await runGuard(mock, "owner");
    expect(result).toBe(true);
  });
});
