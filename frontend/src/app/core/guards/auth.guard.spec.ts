import { TestBed } from "@angular/core/testing";
import {
  Router,
  UrlTree,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
} from "@angular/router";
import { provideRouter } from "@angular/router";
import { authGuard } from "./auth.guard";
import { AuthService } from "../services/auth.service";
import { of, throwError, tap } from "rxjs";
import { signal, computed, Signal } from "@angular/core";

describe("authGuard", () => {
  let authServiceMock: {
    isAuthenticatedSignal: Signal<boolean>;
    fetchProfile: ReturnType<typeof vi.fn>;
    currentUserSignal: ReturnType<typeof signal>;
  };
  let router: Router;

  const dummyRoute = {} as ActivatedRouteSnapshot;
  const dummyState = {} as RouterStateSnapshot;

  function createAuthService(isAuthenticated: boolean) {
    const userSignal = signal(isAuthenticated ? { role: "user" } : null);
    return {
      isAuthenticatedSignal: computed(() => !!userSignal()),
      currentUserSignal: userSignal,
      fetchProfile: vi.fn(),
    };
  }

  async function runGuard(
    mock: typeof authServiceMock,
  ): Promise<boolean | UrlTree> {
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: mock }],
    }).compileComponents();
    router = TestBed.inject(Router);
    return TestBed.runInInjectionContext(() =>
      authGuard(dummyRoute, dummyState),
    ) as Promise<boolean | UrlTree>;
  }

  it("should allow navigation when user is authenticated", async () => {
    authServiceMock = createAuthService(true);
    const result = await runGuard(authServiceMock);
    expect(result).toBe(true);
  });

  it("should try fetchProfile and allow if session restores", async () => {
    const userSignal = signal<{ role: string } | null>(null);
    authServiceMock = {
      isAuthenticatedSignal: computed(() => !!userSignal()),
      currentUserSignal: userSignal,
      fetchProfile: vi.fn().mockReturnValue(
        of({ role: "user" }).pipe(
          // Simulate the tap that sets the signal in real AuthService
          tap(() => userSignal.set({ role: "user" })),
        ),
      ),
    };

    // After fetchProfile resolves, isAuthenticatedSignal should be true
    // But since guard checks isAuthenticatedSignal after await, we need
    // the signal to update during fetchProfile execution
    const result = await runGuard(authServiceMock);
    expect(authServiceMock.fetchProfile).toHaveBeenCalled();
    expect(result).toBe(true);
  });

  it("should redirect to /login when fetchProfile fails", async () => {
    authServiceMock = createAuthService(false);
    authServiceMock.fetchProfile.mockReturnValue(
      throwError(() => new Error("Unauthorized")),
    );

    const result = await runGuard(authServiceMock);
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe("/login");
  });

  it("should redirect to /login when not authenticated and no session", async () => {
    const userSignal = signal(null);
    authServiceMock = {
      isAuthenticatedSignal: computed(() => false),
      currentUserSignal: userSignal,
      fetchProfile: vi.fn().mockReturnValue(of(null)),
    };

    const result = await runGuard(authServiceMock);
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe("/login");
  });
});
