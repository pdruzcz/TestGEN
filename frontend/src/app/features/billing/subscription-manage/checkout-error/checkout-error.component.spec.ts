import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { CheckoutErrorComponent } from "./checkout-error.component";

describe("CheckoutErrorComponent", () => {
  let fixture: ComponentFixture<CheckoutErrorComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CheckoutErrorComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CheckoutErrorComponent);
    fixture.detectChanges();
  });

  it("komunikat: transakcja przerwana, plan bez zmian (AC6)", () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Płatność nie została zakończona");
    expect(text).toContain("Twój plan pozostaje bez zmian");
    expect(text).toContain("ponowić próbę");
  });

  it("CTA wraca do strony planów, by ponowić checkout (AC6)", () => {
    const cta = fixture.nativeElement.querySelector(
      "a[mat-flat-button]",
    ) as HTMLAnchorElement;
    expect(cta).toBeTruthy();
    expect(cta.getAttribute("href")).toContain("/billing/plans");
    expect(cta.textContent?.trim()).toContain("Spróbuj ponownie");
  });
});
