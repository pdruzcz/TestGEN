import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { ActivatedRoute, convertToParamMap } from "@angular/router";
import { SetPasswordComponent } from "./set-password.component";
import { environment } from "../../../../environments/environment";

function createActivatedRoute(token: string | null) {
  return {
    snapshot: {
      queryParamMap: convertToParamMap(token ? { token } : {}),
    },
  };
}

describe("SetPasswordComponent", () => {
  let component: SetPasswordComponent;
  let fixture: ComponentFixture<SetPasswordComponent>;
  let httpTesting: HttpTestingController;

  function setup(token: string | null = "abc123def456") {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [SetPasswordComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: createActivatedRoute(token) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SetPasswordComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting.verify();
  });

  it("should create", () => {
    setup();
    expect(component).toBeTruthy();
  });

  describe("token validation", () => {
    it("should set tokenError when no token in URL", () => {
      setup(null);
      expect(component.tokenError()).toBe("Brak tokena zaproszenia w linku");
    });

    it("should set tokenError for invalid token format", () => {
      setup("invalid!token@#$");
      expect(component.tokenError()).toBe("Nieprawidłowy format tokena");
    });

    it("should accept valid hex token", () => {
      setup("aabbccdd11223344");
      expect(component.tokenError()).toBe("");
    });

    it("should show token error in template", () => {
      setup(null);
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector(".error")).toBeTruthy();
      expect(el.textContent).toContain("Brak tokena zaproszenia w linku");
    });
  });

  describe("form validation", () => {
    beforeEach(() => setup());

    it("should be invalid when empty", () => {
      expect(component.form.valid).toBe(false);
    });

    it("should require password", () => {
      expect(component.form.controls.password.hasError("required")).toBe(true);
    });

    it("should require password min 12 chars", () => {
      component.form.controls.password.setValue("Short1!");
      expect(component.form.controls.password.hasError("minlength")).toBe(true);
    });

    it("should require password complexity", () => {
      component.form.controls.password.setValue("simplepassword");
      expect(
        component.form.controls.password.hasError("passwordComplexity"),
      ).toBe(true);
    });

    it("should accept complex password", () => {
      component.form.controls.password.setValue("StrongPass123!");
      expect(
        component.form.controls.password.hasError("passwordComplexity"),
      ).toBe(false);
      expect(component.form.controls.password.hasError("minlength")).toBe(
        false,
      );
    });

    it("should validate password match", () => {
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("DifferentPass456!");
      expect(component.form.hasError("passwordMismatch")).toBe(true);
    });

    it("should pass when passwords match", () => {
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
      expect(component.form.hasError("passwordMismatch")).toBe(false);
    });
  });

  describe("form submission", () => {
    function fillValidForm(): void {
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
    }

    beforeEach(() => setup("abc123def456"));

    it("should not submit when form is invalid", () => {
      component.onSubmit();
      httpTesting.expectNone(`${environment.apiUrl}/auth/accept-invitation`);
    });

    it("should call acceptInvitation on valid submit", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/auth/accept-invitation`,
      );
      expect(req.request.method).toBe("POST");
      expect(req.request.body.token).toBe("abc123def456");
      expect(req.request.body.password).toBe("StrongPass123!");
      req.flush({ message: "OK" });
    });

    it("should set isSubmitting during request", () => {
      fillValidForm();
      component.onSubmit();
      expect(component.isSubmitting()).toBe(true);

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/auth/accept-invitation`,
      );
      req.flush({ message: "OK" });
      expect(component.isSubmitting()).toBe(false);
    });

    it("should display success message on success", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/auth/accept-invitation`,
      );
      req.flush({ message: "Konto zostało aktywowane" });
      fixture.detectChanges();

      expect(component.successMessage()).toBe("Konto zostało aktywowane");
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector(".success")).toBeTruthy();
      expect(el.textContent).toContain("Hasło ustawione");
    });

    it("should display server error on failure", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/auth/accept-invitation`,
      );
      req.flush(
        { detail: "Token wygasł" },
        { status: 400, statusText: "Bad Request" },
      );

      expect(component.serverError()).toBe("Nie udało się ustawić hasła");
    });

    it("should use default error when no detail in response", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(
        `${environment.apiUrl}/auth/accept-invitation`,
      );
      req.flush(null, { status: 500, statusText: "Server Error" });

      expect(component.serverError()).toBe("Nie udało się ustawić hasła");
    });

    it("should not submit when token is missing", () => {
      setup(null);
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
      component.onSubmit();
      httpTesting.expectNone(`${environment.apiUrl}/auth/accept-invitation`);
    });
  });
});
