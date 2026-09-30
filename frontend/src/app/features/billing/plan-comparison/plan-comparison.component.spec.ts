import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { of } from "rxjs";
import { vi } from "vitest";

import { environment } from "../../../../environments/environment";
import { PlanComparison } from "../billing.service";
import { PlanComparisonComponent } from "./plan-comparison.component";

const mockComparison: PlanComparison = {
  plans: [
    {
      id: "plan-freemium",
      name: "freemium",
      displayName: "Freemium",
      priceMonthly: "0.00",
      currency: "PLN",
      features: {
        analyses: 10,
        testCases: 50,
        storageBytes: 500 * 1024 * 1024,
        filesPerAnalysis: 5,
        rateLimitPerMin: 100,
        prioritySupport: false,
      },
      isActive: true,
      sortOrder: 0,
    },
    {
      id: "plan-basic",
      name: "basic",
      displayName: "Basic",
      priceMonthly: "30.00",
      currency: "PLN",
      features: {
        analyses: 50,
        testCases: 250,
        storageBytes: 5 * 1024 * 1024 * 1024,
        filesPerAnalysis: 25,
        rateLimitPerMin: 100,
        prioritySupport: false,
      },
      isActive: true,
      sortOrder: 1,
    },
    {
      id: "plan-premium",
      name: "premium",
      displayName: "Premium",
      priceMonthly: "50.00",
      currency: "PLN",
      features: {
        analyses: null,
        testCases: null,
        storageBytes: 10 * 1024 * 1024 * 1024,
        filesPerAnalysis: 50,
        rateLimitPerMin: 1000,
        prioritySupport: true,
      },
      isActive: true,
      sortOrder: 2,
    },
  ],
  currentPlan: "basic",
  termsUrl: "https://test-gen.pl/regulamin/",
  privacyPolicyUrl: "https://test-gen.pl/polityka/",
};

async function setup(): Promise<{
  fixture: ComponentFixture<PlanComparisonComponent>;
  httpMock: HttpTestingController;
}> {
  await TestBed.configureTestingModule({
    imports: [PlanComparisonComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      NoopAnimationsModule,
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(PlanComparisonComponent);
  return { fixture, httpMock: TestBed.inject(HttpTestingController) };
}

function flushPlans(
  httpMock: HttpTestingController,
  body: PlanComparison = mockComparison,
): void {
  const req = httpMock.expectOne(`${environment.apiUrl}/billing/plans`);
  expect(req.request.method).toBe("GET");
  req.flush(body);
}

describe("PlanComparisonComponent", () => {
  it("tworzy się i pobiera plany z GET /billing/plans", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
    expect(fixture.componentInstance.plans().length).toBe(3);
    httpMock.verify();
  });

  it("renderuje 3 plany z cenami 0/30/50 PLN (AC1/AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Freemium");
    expect(text).toContain("Basic");
    expect(text).toContain("Premium");
    expect(text).toContain("0.00");
    expect(text).toContain("30.00");
    expect(text).toContain("50.00");
    expect(text).toContain("PLN / mies.");
  });

  it("oznacza aktualny plan etykietą „Twój aktualny plan” (AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Twój aktualny plan");
    expect(fixture.componentInstance.isCurrent("basic")).toBe(true);
    expect(fixture.componentInstance.isCurrent("freemium")).toBe(false);

    // Wyróżniona karta aktualnego planu
    const currentCard = fixture.nativeElement.querySelector(
      "mat-card.plan-card.current",
    );
    expect(currentCard).toBeTruthy();
  });

  it("z Freemium renderuje CTA „Wybierz Premium” kierujące do checkout (AC3/7.4)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock, { ...mockComparison, currentPlan: "freemium" });
    fixture.detectChanges();

    const cta = fixture.nativeElement.querySelector(
      "a[mat-flat-button]",
    ) as HTMLAnchorElement;
    expect(cta).toBeTruthy();
    expect(cta.textContent?.trim()).toBe("Wybierz Basic");

    const href = cta.getAttribute("href");
    expect(href).toContain("/billing/checkout");
    expect(href).toContain("plan=basic");
  });

  it("nie renderuje CTA dla planu aktualnego i darmowego", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock, { ...mockComparison, currentPlan: "freemium" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).not.toContain("Wybierz Freemium");
    expect(text).toContain("Plan aktywny"); // freemium = aktualny
  });

  it("bez subskrypcji karta Freemium pokazuje notkę startową", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock, { ...mockComparison, currentPlan: null });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Plan startowy — bez karty płatniczej");
  });

  // --- Story 7.5 (AC7): dynamiczne przyciski zmiany planu ---

  it("na planie płatnym renderuje „Przejdź na Premium” i „Obniż do Freemium” (7.5 AC7)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock); // currentPlan: basic
    fixture.detectChanges();

    const buttons: HTMLButtonElement[] = Array.from(
      fixture.nativeElement.querySelectorAll("button[mat-flat-button]"),
    );
    const labels = buttons.map((b) => b.textContent?.trim());
    expect(labels).toContain("Przejdź na Premium");
    expect(labels).toContain("Obniż do Freemium");
    // Brak linku checkoutowego — zmiana idzie przez dialog (7.5), nie 7.4
    expect(
      fixture.nativeElement.querySelector("a[mat-flat-button]"),
    ).toBeNull();
  });

  it("klik „Przejdź na Premium” otwiera dialog potwierdzenia (7.5 AC5/AC7)", async () => {
    const { MatDialog } = await import("@angular/material/dialog");
    const { fixture, httpMock } = await setup();
    const dialog = TestBed.inject(MatDialog);
    const openSpy = vi
      .spyOn(dialog, "open")
      .mockReturnValue({ afterClosed: () => of(undefined) } as never);

    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const buttons: HTMLButtonElement[] = Array.from(
      fixture.nativeElement.querySelectorAll("button[mat-flat-button]"),
    );
    const upgrade = buttons.find(
      (b) => b.textContent?.trim() === "Przejdź na Premium",
    );
    expect(upgrade).toBeTruthy();
    upgrade?.click();

    expect(openSpy).toHaveBeenCalledTimes(1);
    const config = openSpy.mock.calls[0][1] as {
      data: { targetPlan: { name: string }; currentPlan: { name: string } };
    };
    expect(config.data.targetPlan.name).toBe("premium");
    expect(config.data.currentPlan.name).toBe("basic");
  });

  it("po dialogu z paymentUrl przekierowuje na checkout tpay (7.5 AC1)", async () => {
    const { MatDialog } = await import("@angular/material/dialog");
    const { fixture, httpMock } = await setup();
    const dialog = TestBed.inject(MatDialog);
    vi.spyOn(dialog, "open").mockReturnValue({
      afterClosed: () =>
        of({
          change: {},
          changeType: "upgrade",
          amount: "10.00",
          currency: "PLN",
          paymentRequired: true,
          paymentUrl: "https://secure.tpay.com/panel/x",
          orderId: "ord-1",
        }),
    } as never);
    // window.location — podmiana na zapisywalny obiekt (jsdom)
    const original = window.location;
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: "" } as Location,
    });

    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    fixture.componentInstance.openChangeDialog(
      mockComparison.plans.find((p) => p.name === "premium")!,
    );

    expect(window.location.href).toBe("https://secure.tpay.com/panel/x");
    Object.defineProperty(window, "location", {
      writable: true,
      value: original,
    });
  });

  it("renderuje tabelę porównawczą z wartościami macierzy (AC1)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Analizy / mies.");
    expect(text).toContain("Bez limitu"); // premium analyses/testCases
    expect(text).toContain("500 MB");
    expect(text).toContain("5 GB");
    expect(text).toContain("10 GB");
    expect(text).toContain("Priorytetowe wsparcie");

    const table = fixture.nativeElement.querySelector("table.comparison-table");
    expect(table).toBeTruthy();
    expect(table.querySelector("caption")?.textContent).toContain(
      "Porównanie funkcji planów",
    );
  });

  it("renderuje linki prawne z konfiguracji backendu (AC3 — wymóg tpay)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const links: HTMLAnchorElement[] = Array.from(
      fixture.nativeElement.querySelectorAll(".legal-links a"),
    );
    expect(links.length).toBe(2);
    expect(links[0].getAttribute("href")).toBe(
      "https://test-gen.pl/regulamin/",
    );
    expect(links[0].textContent).toContain("Regulamin");
    expect(links[1].getAttribute("href")).toBe("https://test-gen.pl/polityka/");
    expect(links[1].textContent).toContain("Polityka prywatności");
  });

  it("pokazuje komunikat błędu, gdy API zwraca błąd", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    const req = httpMock.expectOne(`${environment.apiUrl}/billing/plans`);
    req.flush("error", { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nie udało się pobrać planów subskrypcji");
    expect(fixture.componentInstance.loading()).toBe(false);
  });
});
