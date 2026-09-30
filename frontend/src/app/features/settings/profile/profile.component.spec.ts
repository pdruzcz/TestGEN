import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { ProfileComponent } from "./profile.component";
import { AuthService, UserProfile } from "../../../core/services/auth.service";
import { environment } from "../../../../environments/environment";
import { signal, WritableSignal } from "@angular/core";
import { of, throwError } from "rxjs";

const mockUser: UserProfile = {
  id: "u1",
  tenantId: "t1",
  email: "jan@example.com",
  name: "Jan Kowalski",
  role: "owner",
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
    fetchProfile: vi.fn().mockReturnValue(of(mockUser)),
    updateCurrentUser: vi.fn(),
  };
}

describe("ProfileComponent", () => {
  let component: ProfileComponent;
  let fixture: ComponentFixture<ProfileComponent>;
  let httpTesting: HttpTestingController;
  let authServiceMock: ReturnType<typeof createAuthServiceMock>;

  beforeEach(async () => {
    authServiceMock = createAuthServiceMock();

    await TestBed.configureTestingModule({
      imports: [ProfileComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: authServiceMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    // Dzwonek powiadomień w navbarze (Story 7.11) odpytuje unread-count
    // po asynchronicznej emisji toObservable — czekamy na zapytanie.
    await new Promise((resolve) => setTimeout(resolve, 10));
    httpTesting
      .expectOne(`${environment.apiUrl}/notifications/unread-count`)
      .flush({ count: 0 });
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should load user data into profile form on init", () => {
    expect(component.user()).toEqual(mockUser);
    expect(component.profileForm.controls.name.value).toBe("Jan Kowalski");
  });

  it("should display email as readonly", () => {
    const el = fixture.nativeElement as HTMLElement;
    const emailInput = el.querySelector(
      'input[type="email"]',
    ) as HTMLInputElement;
    expect(emailInput).toBeTruthy();
    expect(emailInput.readOnly).toBe(true);
    expect(emailInput.value).toBe("jan@example.com");
  });

  describe("profile update", () => {
    it("should not submit when form is invalid (name too long)", () => {
      component.profileForm.controls.name.setValue("a".repeat(256));
      component.onUpdateProfile();
      httpTesting.expectNone(`${environment.apiUrl}/users/me`);
    });

    it("should call PUT /users/me on valid submit", () => {
      component.profileForm.controls.name.setValue("Nowa Nazwa");
      component.onUpdateProfile();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/me`);
      expect(req.request.method).toBe("PUT");
      expect(req.request.body.name).toBe("Nowa Nazwa");
      req.flush({ ...mockUser, name: "Nowa Nazwa" });

      expect(component.profileMessage()).toBe("Profil zaktualizowany");
      expect(component.isSubmittingProfile()).toBe(false);
    });

    it("should show error message on profile update failure", () => {
      component.profileForm.controls.name.setValue("Test");
      component.onUpdateProfile();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/me`);
      req.flush(null, { status: 500, statusText: "Server Error" });

      expect(component.profileMessage()).toBe("Błąd aktualizacji profilu");
      expect(component.isSubmittingProfile()).toBe(false);
    });

    it("should set isSubmittingProfile during request", () => {
      component.profileForm.controls.name.setValue("Test");
      component.onUpdateProfile();
      expect(component.isSubmittingProfile()).toBe(true);

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/me`);
      req.flush({ ...mockUser, name: "Test" });
      expect(component.isSubmittingProfile()).toBe(false);
    });
  });

  describe("notification preferences (Story 7.11, AC5)", () => {
    it("domyślnie oba kanały włączone przy braku zapisanych preferencji", () => {
      expect(component.emailNotifications()).toBe(true);
      expect(component.inAppNotifications()).toBe(true);
    });

    it("odczytuje wyłączone kanały z profilu", () => {
      authServiceMock.currentUserSignal.set({
        ...mockUser,
        notificationPreferences: {
          limitWarnings: { email: false, inApp: false },
        },
      });
      component.ngOnInit();
      expect(component.emailNotifications()).toBe(false);
      expect(component.inAppNotifications()).toBe(false);
    });

    it("zapis wysyła PUT /users/me z notificationPreferences", () => {
      component.emailNotifications.set(false);
      component.onSavePreferences();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/me`);
      expect(req.request.method).toBe("PUT");
      expect(req.request.body.notificationPreferences).toEqual({
        limitWarnings: { email: false, inApp: true },
      });
      req.flush({
        ...mockUser,
        notificationPreferences: {
          limitWarnings: { email: false, inApp: true },
        },
      });
      fixture.detectChanges();

      expect(component.profileMessage()).toBe(
        "Preferencje powiadomień zapisane",
      );
      expect(authServiceMock.updateCurrentUser).toHaveBeenCalled();
    });
  });

  describe("password change", () => {
    it("should require old password", () => {
      expect(
        component.passwordForm.controls.oldPassword.hasError("required"),
      ).toBe(true);
    });

    it("should require new password min 12 chars", () => {
      component.passwordForm.controls.newPassword.setValue("short");
      expect(
        component.passwordForm.controls.newPassword.hasError("minlength"),
      ).toBe(true);
    });

    it("should validate password match", () => {
      component.passwordForm.controls.oldPassword.setValue("OldPass123!xx");
      component.passwordForm.controls.newPassword.setValue("StrongPass123!");
      component.passwordForm.controls.confirmNewPassword.setValue(
        "DifferentPass456!",
      );
      expect(component.passwordForm.hasError("passwordMismatch")).toBe(true);
    });

    it("should not submit when password form is invalid", () => {
      component.onChangePassword();
      httpTesting.expectNone(`${environment.apiUrl}/users/me/password`);
    });

    it("should call PUT /users/me/password on valid submit", () => {
      component.passwordForm.controls.oldPassword.setValue("OldPassword123!");
      component.passwordForm.controls.newPassword.setValue("NewPassword123!");
      component.passwordForm.controls.confirmNewPassword.setValue(
        "NewPassword123!",
      );
      component.onChangePassword();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/users/me/password`,
      );
      expect(req.request.method).toBe("PUT");
      expect(req.request.body.oldPassword).toBe("OldPassword123!");
      expect(req.request.body.newPassword).toBe("NewPassword123!");
      req.flush({});

      expect(component.passwordMessage()).toBe("Hasło zmienione pomyślnie");
      expect(component.passwordError()).toBe(false);
      expect(component.isSubmittingPassword()).toBe(false);
    });

    it("should show error on password change failure", () => {
      component.passwordForm.controls.oldPassword.setValue("OldPassword123!");
      component.passwordForm.controls.newPassword.setValue("NewPassword123!");
      component.passwordForm.controls.confirmNewPassword.setValue(
        "NewPassword123!",
      );
      component.onChangePassword();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/users/me/password`,
      );
      req.flush(
        { detail: "Nieprawidłowe obecne hasło" },
        { status: 400, statusText: "Bad Request" },
      );

      expect(component.passwordMessage()).toBe(
        "Błąd zmiany hasła. Sprawdź poprawność danych.",
      );
      expect(component.passwordError()).toBe(true);
    });

    it("should use default error when no detail in response", () => {
      component.passwordForm.controls.oldPassword.setValue("OldPassword123!");
      component.passwordForm.controls.newPassword.setValue("NewPassword123!");
      component.passwordForm.controls.confirmNewPassword.setValue(
        "NewPassword123!",
      );
      component.onChangePassword();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/users/me/password`,
      );
      req.flush(null, { status: 500, statusText: "Server Error" });

      expect(component.passwordMessage()).toBe(
        "Błąd zmiany hasła. Sprawdź poprawność danych.",
      );
    });
  });
});
