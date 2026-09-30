import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { ActivatedRoute, convertToParamMap } from "@angular/router";
import { EmailVerificationComponent } from "./email-verification.component";
import { environment } from "../../../../environments/environment";

function createActivatedRoute(token: string | null) {
  return {
    snapshot: {
      queryParamMap: convertToParamMap(token ? { token } : {}),
    },
  };
}

describe("EmailVerificationComponent", () => {
  let component: EmailVerificationComponent;
  let fixture: ComponentFixture<EmailVerificationComponent>;
  let httpTesting: HttpTestingController;

  function setup(token: string | null = "abc123def456") {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [EmailVerificationComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: createActivatedRoute(token) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EmailVerificationComponent);
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

  it("should extract token from query params on init", () => {
    setup("aabbccdd1122");
    expect(component.token()).toBe("aabbccdd1122");
  });

  it("should set null token when no token in URL", () => {
    setup(null);
    expect(component.token()).toBeNull();
  });

  it("should reject invalid token format (non-hex characters)", () => {
    setup("not-a-valid-hex!@#");
    expect(component.token()).toBeNull();
  });

  it("should show missing token error when no token provided", () => {
    setup(null);
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain("Brak tokena weryfikacyjnego");
  });

  it("should show verify button when valid token is present", () => {
    setup("abc123def456");
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector("button")?.textContent).toContain(
      "Zweryfikuj email",
    );
  });

  it("should call verifyEmail API when verify button is clicked", () => {
    setup("abc123def456");
    component.verify();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/auth/verify-email`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body.token).toBe("abc123def456");
    req.flush({ message: "OK" });
  });

  it("should set isVerifying during verification request", () => {
    setup("abc123def456");
    component.verify();
    expect(component.isVerifying()).toBe(true);

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/auth/verify-email`,
    );
    req.flush({ message: "OK" });
    expect(component.isVerifying()).toBe(false);
  });

  it("should display success message on successful verification", () => {
    setup("abc123def456");
    component.verify();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/auth/verify-email`,
    );
    req.flush({ message: "Email zweryfikowany pomyślnie" });
    fixture.detectChanges();

    expect(component.successMessage()).toBe("Email zweryfikowany pomyślnie");
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector(".success")).toBeTruthy();
    expect(el.textContent).toContain("Email zweryfikowany");
  });

  it("should display error message on failed verification", () => {
    setup("abc123def456");
    component.verify();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/auth/verify-email`,
    );
    req.flush(
      { detail: "Token wygasł" },
      { status: 400, statusText: "Bad Request" },
    );
    fixture.detectChanges();

    expect(component.errorMessage()).toBe(
      "Token jest nieprawidłowy lub wygasł.",
    );
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector(".error")).toBeTruthy();
  });

  it("should use default error message when no detail in response", () => {
    setup("abc123def456");
    component.verify();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/auth/verify-email`,
    );
    req.flush(null, { status: 500, statusText: "Server Error" });

    expect(component.errorMessage()).toBe(
      "Token jest nieprawidłowy lub wygasł.",
    );
  });

  it("should not call API when token is empty", () => {
    setup(null);
    component.verify();
    httpTesting.expectNone(`${environment.apiUrl}/auth/verify-email`);
  });
});
