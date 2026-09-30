import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { signal, WritableSignal } from "@angular/core";
import { NavbarComponent } from "./navbar.component";
import { AuthService, UserProfile } from "../../core/services/auth.service";

const mockUser: UserProfile = {
  id: "u1",
  tenantId: "t1",
  email: "jan@example.com",
  name: "Jan Kowalski",
  role: "user",
  isActive: true,
  emailVerifiedAt: "2026-01-01T00:00:00Z",
  notificationPreferences: {},
  mfaEnabled: false,
};

function createAuthServiceMock(user: UserProfile | null = mockUser) {
  return {
    currentUserSignal: signal<UserProfile | null>(
      user,
    ) as WritableSignal<UserProfile | null>,
    logout: vi.fn(),
    fetchProfile: vi.fn(),
    updateCurrentUser: vi.fn(),
  };
}

describe("NavbarComponent", () => {
  let component: NavbarComponent;
  let fixture: ComponentFixture<NavbarComponent>;
  let authServiceMock: ReturnType<typeof createAuthServiceMock>;

  beforeEach(async () => {
    authServiceMock = createAuthServiceMock();

    await TestBed.configureTestingModule({
      imports: [NavbarComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NavbarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should render the logo", () => {
    const el = fixture.nativeElement as HTMLElement;
    const img = el.querySelector(".nav-logo-img") as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.src).toContain("logo.svg");
  });

  it("should render all four nav links", () => {
    const el = fixture.nativeElement as HTMLElement;
    const pills = el.querySelectorAll(".nav-pill");
    expect(pills.length).toBe(4);
    expect(pills[0].textContent).toContain("Dashboard");
    expect(pills[1].textContent).toContain("Projekty");
    expect(pills[2].textContent).toContain("Rozliczenia");
    expect(pills[3].textContent).toContain("Profil");
  });

  it("should open billing menu with base and owner-only entries for owner", async () => {
    authServiceMock.currentUserSignal.set({ ...mockUser, role: "owner" });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    (
      el.querySelector(".nav-pill[aria-haspopup='menu']") as HTMLElement
    ).click();
    await fixture.whenStable();

    const items = Array.from(document.querySelectorAll(".mat-mdc-menu-item"));
    const labels = items.map((i) => i.textContent ?? "");
    expect(labels.some((l) => l.includes("Plany subskrypcji"))).toBe(true);
    expect(labels.some((l) => l.includes("Zużycie zasobów"))).toBe(true);
    expect(labels.some((l) => l.includes("Faktury"))).toBe(true);
    expect(labels.some((l) => l.includes("Dane fakturowe"))).toBe(true);
    expect(labels.some((l) => l.includes("Metody płatności"))).toBe(true);
  });

  it("should hide owner-only billing entries for regular user", async () => {
    const el = fixture.nativeElement as HTMLElement;
    (
      el.querySelector(".nav-pill[aria-haspopup='menu']") as HTMLElement
    ).click();
    await fixture.whenStable();

    const items = Array.from(document.querySelectorAll(".mat-mdc-menu-item"));
    const labels = items.map((i) => i.textContent ?? "");
    expect(labels.some((l) => l.includes("Plany subskrypcji"))).toBe(true);
    expect(labels.some((l) => l.includes("Metody płatności"))).toBe(false);
    expect(labels.some((l) => l.includes("Dane fakturowe"))).toBe(false);
  });

  it("should highlight the default active link (dashboard)", () => {
    const el = fixture.nativeElement as HTMLElement;
    const activePill = el.querySelector(".nav-active");
    expect(activePill?.textContent).toContain("Dashboard");
  });

  it("should display user initials in avatar", () => {
    const el = fixture.nativeElement as HTMLElement;
    const avatar = el.querySelector(".nav-avatar");
    expect(avatar?.textContent?.trim()).toBe("JK");
  });

  it("should have a logout button", () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector(".nav-logout")).toBeTruthy();
  });

  it("should call authService.logout on logout click", () => {
    const el = fixture.nativeElement as HTMLElement;
    const logoutBtn = el.querySelector(".nav-logout") as HTMLElement;
    logoutBtn.click();
    expect(authServiceMock.logout).toHaveBeenCalled();
  });

  it("should show ? when no user name", () => {
    authServiceMock.currentUserSignal.set(null);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const avatar = el.querySelector(".nav-avatar");
    expect(avatar?.textContent?.trim()).toBe("?");
  });
});
