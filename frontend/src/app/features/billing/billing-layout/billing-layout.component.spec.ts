import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { provideRouter } from "@angular/router";
import { ComponentFixture, TestBed } from "@angular/core/testing";

import { BillingLayoutComponent } from "./billing-layout.component";

describe("BillingLayoutComponent", () => {
  let fixture: ComponentFixture<BillingLayoutComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BillingLayoutComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(BillingLayoutComponent);
    fixture.detectChanges();
  });

  it("tworzy się", () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it("renderuje navbar z aktywną pozycją Rozliczenia", () => {
    const el = fixture.nativeElement as HTMLElement;
    const active = el.querySelector("a.nav-pill.nav-active");
    expect(active?.textContent?.trim()).toContain("Rozliczenia");
  });

  it("ma główny obszar treści (cel skip-linku) i stopkę", () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector("main#main-content")).toBeTruthy();
    expect(el.querySelector("footer.app-footer")).toBeTruthy();
  });

  it("zawiera outlet na strony potomne", () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector("main router-outlet")).toBeTruthy();
  });
});
