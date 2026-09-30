import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { RegisterComponent } from "./register.component";
import { environment } from "../../../../environments/environment";

describe("RegisterComponent", () => {
  let component: RegisterComponent;
  let fixture: ComponentFixture<RegisterComponent>;
  let httpTesting: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RegisterComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(RegisterComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  describe("form validation", () => {
    it("should be invalid when empty", () => {
      expect(component.form.valid).toBe(false);
    });

    it("should require email", () => {
      expect(component.form.controls.email.hasError("required")).toBe(true);
    });

    it("should validate email format", () => {
      component.form.controls.email.setValue("not-an-email");
      expect(component.form.controls.email.hasError("email")).toBe(true);
    });

    it("should accept valid email", () => {
      component.form.controls.email.setValue("test@example.com");
      expect(component.form.controls.email.hasError("email")).toBe(false);
    });

    it("should require password min 12 chars", () => {
      component.form.controls.password.setValue("short");
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

    it("should require company name", () => {
      expect(component.form.controls.companyName.hasError("required")).toBe(
        true,
      );
    });

    it("should validate NIP pattern (10 digits)", () => {
      component.form.controls.nip.setValue("abc");
      expect(component.form.controls.nip.hasError("pattern")).toBe(true);
    });

    it("should accept valid NIP", () => {
      component.form.controls.nip.setValue("1234567890");
      expect(component.form.controls.nip.hasError("pattern")).toBe(false);
    });

    it("should allow empty NIP (optional)", () => {
      component.form.controls.nip.setValue("");
      expect(component.form.controls.nip.valid).toBe(true);
    });
  });

  describe("form submission", () => {
    function fillValidForm(): void {
      component.form.controls.email.setValue("test@example.com");
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
      component.form.controls.companyName.setValue("Test Corp");
    }

    it("should not submit when form is invalid", () => {
      component.onSubmit();
      httpTesting.expectNone(`${environment.apiUrl}/auth/register`);
    });

    it("should call register on valid submit", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body.email).toBe("test@example.com");
      expect(req.request.body.companyName).toBe("Test Corp");
      req.flush({ email: "test@example.com", message: "Check email" });
    });

    it("should set isSubmitting during request", () => {
      fillValidForm();
      component.onSubmit();
      expect(component.isSubmitting()).toBe(true);

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush({ email: "test@example.com", message: "ok" });
      expect(component.isSubmitting()).toBe(false);
    });

    it("should display success message on success", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush({
        email: "test@example.com",
        message: "Sprawdź swoją skrzynkę email",
      });

      expect(component.successMessage()).toBe("Sprawdź swoją skrzynkę email");
    });

    it("should display error message on failure", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush(
        { detail: "Email already registered" },
        { status: 409, statusText: "Conflict" },
      );

      expect(component.errorMessage()).toBe(
        "Wystąpił błąd rejestracji. Spróbuj ponownie.",
      );
    });

    it("should use default error when no detail", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush(null, { status: 500, statusText: "Server Error" });

      expect(component.errorMessage()).toBe(
        "Wystąpił błąd rejestracji. Spróbuj ponownie.",
      );
    });

    it("should send nip when provided", () => {
      fillValidForm();
      component.form.controls.nip.setValue("1234567890");
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      expect(req.request.body.nip).toBe("1234567890");
      req.flush({ email: "test@example.com", message: "ok" });
    });

    it("should not send nip when empty", () => {
      fillValidForm();
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      expect(req.request.body.nip).toBeUndefined();
      req.flush({ email: "test@example.com", message: "ok" });
    });
  });

  describe("template rendering", () => {
    it("should show form initially", () => {
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector("form")).toBeTruthy();
    });

    it("should show success and hide form after successful registration", () => {
      component.form.controls.email.setValue("test@example.com");
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
      component.form.controls.companyName.setValue("Test Corp");
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush({ email: "test@example.com", message: "Email sent" });
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector(".success-banner")).toBeTruthy();
      expect(el.querySelector("form")).toBeFalsy();
    });

    it("should show error message in template", () => {
      component.form.controls.email.setValue("test@example.com");
      component.form.controls.password.setValue("StrongPass123!");
      component.form.controls.confirmPassword.setValue("StrongPass123!");
      component.form.controls.companyName.setValue("Test Corp");
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/auth/register`);
      req.flush(
        { detail: "Registration failed" },
        { status: 400, statusText: "Bad Request" },
      );
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector(".error-banner")?.textContent).toContain(
        "Wystąpił błąd rejestracji",
      );
    });
  });
});
