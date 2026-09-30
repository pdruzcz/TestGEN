import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { QuotaAlertService } from "../../interceptors/quota-interceptor";
import { QuotaExceededBannerComponent } from "./quota-exceeded-banner.component";

describe("QuotaExceededBannerComponent (Story 7.8, AC6)", () => {
  let fixture: ComponentFixture<QuotaExceededBannerComponent>;
  let alerts: QuotaAlertService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QuotaExceededBannerComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    alerts = TestBed.inject(QuotaAlertService);
    alerts.dismiss();
    fixture = TestBed.createComponent(QuotaExceededBannerComponent);
    fixture.detectChanges();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  it("nie renderuje niczego bez alertu", () => {
    expect(el().querySelector('[data-testid="quota-banner"]')).toBeNull();
  });

  it("pokazuje komunikat AC6 z zasobem i planem", () => {
    alerts.show({ resource: "analyses", limit: 10, current: 10, plan: "freemium" });
    fixture.detectChanges();

    const banner = el().querySelector('[data-testid="quota-banner"]');
    expect(banner).not.toBeNull();
    expect(banner!.textContent).toContain(
      "Osiągnąłeś limit analiz w planie Freemium. Uaktualnij plan, aby uzyskać wyższe limity.",
    );
  });

  it("CTA 'Uaktualnij plan' prowadzi do /billing/plans", () => {
    alerts.show({ resource: "test_cases", limit: 100, current: 100, plan: "basic" });
    fixture.detectChanges();

    const cta = el().querySelector<HTMLAnchorElement>(
      '[data-testid="quota-upgrade-cta"]',
    );
    expect(cta).not.toBeNull();
    expect(cta!.textContent).toContain("Uaktualnij plan");
    expect(cta!.getAttribute("href")).toBe("/billing/plans");
  });

  it("przycisk zamknięcia ukrywa banner", () => {
    alerts.show({ resource: "storage_bytes", limit: 1, current: 1, plan: "premium" });
    fixture.detectChanges();

    el()
      .querySelector<HTMLButtonElement>('button[aria-label="Zamknij komunikat o limicie"]')!
      .click();
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="quota-banner"]')).toBeNull();
    expect(alerts.alert()).toBeNull();
  });

  it("nieznany zasób/plan pokazywany dosłownie", () => {
    alerts.show({ resource: "custom", limit: null, current: null, plan: "vip" });
    fixture.detectChanges();

    expect(el().textContent).toContain("Osiągnąłeś limit custom w planie vip.");
  });
});
