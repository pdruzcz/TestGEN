import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { UsageDashboard } from "../billing.service";
import { UsageDashboardComponent } from "./usage-dashboard.component";

const mockDashboard: UsageDashboard = {
  currentPeriod: { start: "2026-09-01T00:00:00Z", end: "2026-09-30T00:00:00Z" },
  plan: "freemium",
  counters: [
    { type: "analyses", value: 7, limit: 10, percentage: 70 },
    { type: "testCases", value: 0, limit: 50, percentage: 0 },
    {
      type: "storageBytes",
      value: 367001600,
      limit: 524288000,
      percentage: 70,
    },
    { type: "filesPerAnalysis", value: 3, limit: 5, percentage: 60 },
  ],
  forecast: {
    counterType: "analyses",
    limitDate: "2026-09-25",
    avgDaily: 1,
    daysToLimit: 3,
    exceedsBeforePeriodEnd: true,
  },
  daysRemaining: 20,
};

describe("UsageDashboardComponent (Story 7.9, AC1/AC2/AC4)", () => {
  let fixture: ComponentFixture<UsageDashboardComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UsageDashboardComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(UsageDashboardComponent);
    fixture.detectChanges();
  });

  function flushDashboard(dashboard: UsageDashboard = mockDashboard): void {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/usage/dashboard`,
    );
    expect(req.request.method).toBe("GET");
    req.flush(dashboard);
    fixture.detectChanges();
  }

  it("nagłówek: plan, okres rozliczeniowy i dni do końca (AC2)", () => {
    flushDashboard();

    const text = fixture.nativeElement.querySelector("header").textContent;
    expect(text).toContain("Plan Freemium");
    expect(text).toContain("01.09.2026 — 30.09.2026");
    expect(text).toContain("Pozostało 20 dni");
  });

  it("karty 4 zasobów, bez karty Użytkownicy (AC1)", () => {
    flushDashboard();

    const cards = fixture.nativeElement.querySelectorAll("app-usage-card");
    expect(cards.length).toBe(4);
    const text = fixture.nativeElement.querySelector(".cards-grid").textContent;
    expect(text).toContain("Analizy");
    expect(text).toContain("Przypadki testowe");
    expect(text).toContain("Storage");
    expect(text).toContain("Pliki na analizę");
    expect(text).not.toContain("Użytkownicy");
  });

  it('prognoza z ostrzeżeniem i CTA „Uaktualnij plan" (AC4)', () => {
    flushDashboard();

    const banner = fixture.nativeElement.querySelector(".forecast-banner");
    expect(banner.className).toContain("warning");
    expect(banner.textContent).toContain(
      "Przy obecnym tempie osiągniesz limit analiz około 25.09.2026.",
    );
    const cta = banner.querySelector("a");
    expect(cta).toBeTruthy();
    expect(cta.getAttribute("href")).toBe("/billing/plans");
    expect(cta.textContent).toContain("Uaktualnij plan");
  });

  it("prognoza poza okresem: banner bez ostrzeżenia i bez CTA (AC4)", () => {
    flushDashboard({
      ...mockDashboard,
      forecast: { ...mockDashboard.forecast!, exceedsBeforePeriodEnd: false },
    });

    const banner = fixture.nativeElement.querySelector(".forecast-banner");
    expect(banner.className).not.toContain("warning");
    expect(banner.querySelector("a")).toBeNull();
  });

  it("bez prognozy: brak bannera", () => {
    flushDashboard({ ...mockDashboard, forecast: null });

    expect(fixture.nativeElement.querySelector(".forecast-banner")).toBeNull();
  });

  it("błąd ładowania pokazuje komunikat i retry", () => {
    httpMock
      .expectOne(`${environment.apiUrl}/billing/usage/dashboard`)
      .flush({ error: "x" }, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    const state = fixture.nativeElement.querySelector(".state.error");
    expect(state.textContent).toContain("Nie udało się pobrać danych zużycia");
    expect(state.querySelector("button").textContent).toContain(
      "Spróbuj ponownie",
    );
  });

  it("stan ładowania pokazuje spinner z role=status", () => {
    expect(
      fixture.nativeElement.querySelector(".state[role='status']"),
    ).toBeTruthy();
  });
});
