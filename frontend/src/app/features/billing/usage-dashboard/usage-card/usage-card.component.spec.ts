import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";

import { environment } from "../../../../../environments/environment";
import {
  BillingService,
  UsageDashboardCounter,
  UsageHistory,
} from "../../billing.service";
import { UsageCardComponent } from "./usage-card.component";

function makeCounter(
  overrides: Partial<UsageDashboardCounter>,
): UsageDashboardCounter {
  return {
    type: "analyses",
    value: 7,
    limit: 10,
    percentage: 70,
    ...overrides,
  };
}

const historyResponse: UsageHistory = {
  counterType: "analyses",
  days: 30,
  points: [
    { date: "2026-09-09", value: 5 },
    { date: "2026-09-10", value: 6 },
  ],
};

describe("UsageCardComponent (Story 7.9, AC1/AC3/AC6)", () => {
  let fixture: ComponentFixture<UsageCardComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UsageCardComponent],
      providers: [
        BillingService,
        provideHttpClient(),
        provideHttpClientTesting(),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(UsageCardComponent);
    fixture.componentRef.setInput("counter", makeCounter({}));
    fixture.detectChanges();
  });

  function cardText(): string {
    return fixture.nativeElement.querySelector("mat-card").textContent;
  }

  it('pokazuje nazwę zasobu i wartość „{N} / {limit}" (AC1)', () => {
    expect(cardText()).toContain("Analizy");
    expect(cardText()).toContain("7 / 10");
    expect(cardText()).toContain("70%");
  });

  it('storage w megabajtach „{N} MB / {limit} MB" (AC1)', () => {
    fixture.componentRef.setInput(
      "counter",
      makeCounter({
        type: "storageBytes",
        value: 367001600, // 350 MB
        limit: 524288000, // 500 MB
      }),
    );
    fixture.detectChanges();

    expect(cardText()).toContain("350 MB / 500 MB");
  });

  it('unlimited: „{N} — bez limitu", bez paska i procentu (AC1)', () => {
    fixture.componentRef.setInput(
      "counter",
      makeCounter({ value: 12, limit: null, percentage: null }),
    );
    fixture.detectChanges();

    expect(cardText()).toContain("12 — bez limitu");
    expect(cardText()).toContain("bez limitu");
    expect(fixture.nativeElement.querySelector("mat-progress-bar")).toBeNull();
  });

  it("próg koloru: 70% → warn, 95% → danger, 60% → ok (AC1)", () => {
    const states: [number, string][] = [
      [70, "warn"],
      [95, "danger"],
      [60, "ok"],
    ];
    for (const [percentage, expected] of states) {
      fixture.componentRef.setInput("counter", makeCounter({ percentage }));
      fixture.detectChanges();
      const pct = fixture.nativeElement.querySelector(".pct");
      expect(pct.className).toContain(expected);
    }
  });

  it("pasek ma aria-label z wartością i procentem (AC6)", () => {
    const bar = fixture.nativeElement.querySelector("mat-progress-bar");
    expect(bar.getAttribute("aria-label")).toContain("7 / 10");
    expect(bar.getAttribute("aria-label")).toContain("70%");
  });

  it("rozwinięcie pobiera historię i pokazuje wykres (AC3)", () => {
    fixture.componentInstance.toggle();
    fixture.detectChanges();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/usage/history?counter_type=analyses&days=30`,
    );
    expect(req.request.method).toBe("GET");
    req.flush(historyResponse);
    fixture.detectChanges();

    const details = fixture.nativeElement.querySelector(".details");
    expect(details).toBeTruthy();
    expect(details.querySelector("path.usage-line")).toBeTruthy();
  });

  it("błąd historii pokazuje komunikat i retry (AC3)", () => {
    fixture.componentInstance.toggle();
    fixture.detectChanges();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/usage/history?counter_type=analyses&days=30`,
    );
    req.flush({ error: "server" }, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    const details = fixture.nativeElement.querySelector(".details");
    expect(details.textContent).toContain("Nie udało się pobrać historii");
    expect(details.querySelector("button")).toBeTruthy();
  });

  it("zwinięcie i ponowne rozwinięcie nie powtarza żądania (cache)", () => {
    fixture.componentInstance.toggle();
    fixture.detectChanges();
    httpMock
      .expectOne(
        `${environment.apiUrl}/billing/usage/history?counter_type=analyses&days=30`,
      )
      .flush(historyResponse);
    fixture.detectChanges();

    fixture.componentInstance.toggle(); // zwiń
    fixture.componentInstance.toggle(); // rozwinięcie — bez nowego żądania
    fixture.detectChanges();

    httpMock.verify();
  });

  it("przycisk szczegółów ma aria-expanded i aria-controls (AC6)", () => {
    const button = fixture.nativeElement.querySelector(".details-toggle");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe("usage-details-analyses");
  });
});
