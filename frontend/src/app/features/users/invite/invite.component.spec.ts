import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { InviteComponent } from "./invite.component";
import { environment } from "../../../../environments/environment";

describe("InviteComponent", () => {
  let component: InviteComponent;
  let fixture: ComponentFixture<InviteComponent>;
  let httpTesting: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InviteComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(InviteComponent);
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
    it("should require email", () => {
      expect(component.form.controls.email.hasError("required")).toBe(true);
    });

    it("should validate email format", () => {
      component.form.controls.email.setValue("not-an-email");
      expect(component.form.controls.email.hasError("email")).toBe(true);
    });

    it("should accept valid email", () => {
      component.form.controls.email.setValue("test@example.com");
      expect(component.form.controls.email.valid).toBe(true);
    });

    it("should default role to 'user'", () => {
      expect(component.form.controls.role.value).toBe("user");
    });

    it("should not submit when form is invalid", () => {
      component.onSubmit();
      httpTesting.expectNone(`${environment.apiUrl}/users/invite`);
    });
  });

  describe("form submission", () => {
    beforeEach(() => {
      component.form.controls.email.setValue("zapro@example.com");
      component.form.controls.role.setValue("user");
    });

    it("should call POST /users/invite on valid submit", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      expect(req.request.method).toBe("POST");
      expect(req.request.body.email).toBe("zapro@example.com");
      expect(req.request.body.role).toBe("user");
      req.flush({});
    });

    it("should display success message after successful invite", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush({});

      expect(component.successMessage()).toBe(
        "Zaproszenie wysłane na adres zapro@example.com",
      );
      expect(component.isSubmitting()).toBe(false);
    });

    it("should reset form after successful invite", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush({});

      expect(component.form.controls.email.value).toBe("");
      expect(component.form.controls.role.value).toBe("user");
    });

    it("should set isSubmitting during request", () => {
      component.onSubmit();
      expect(component.isSubmitting()).toBe(true);

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush({});
      expect(component.isSubmitting()).toBe(false);
    });

    it("should show conflict error on 409", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush(
        { detail: "Conflict" },
        { status: 409, statusText: "Conflict" },
      );

      expect(component.errorMessage()).toBe(
        "Użytkownik z tym adresem email już istnieje w Twoim zespole.",
      );
    });

    it("should show forbidden error on 403", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush(
        { detail: "Forbidden" },
        { status: 403, statusText: "Forbidden" },
      );

      expect(component.errorMessage()).toBe(
        "Brak uprawnień do zapraszania użytkowników.",
      );
    });

    it("should show generic error on other failures", () => {
      component.onSubmit();

      const req = httpTesting.expectOne(`${environment.apiUrl}/users/invite`);
      req.flush(null, { status: 500, statusText: "Server Error" });

      expect(component.errorMessage()).toBe("Wystąpił błąd. Spróbuj ponownie.");
    });
  });
});
