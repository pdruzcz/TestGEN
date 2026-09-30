import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MatDialog } from "@angular/material/dialog";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { of } from "rxjs";
import { vi } from "vitest";

import { environment } from "../../../../../environments/environment";
import { SubscriptionDetail } from "../../billing.service";
import { SubscriptionDetailComponent } from "./subscription-detail.component";

const basicDetail: SubscriptionDetail = {
  id: "sub-1",
  tenantId: "t-1",
  planId: "plan-basic",
  status: "active",
  currentPeriodStart: "2026-09-01T00:00:00Z",
  currentPeriodEnd: "2026-09-30T00:00:00Z",
  nextChargeAt: "2026-09-30T00:00:00Z",
  cancelAtPeriodEnd: false,
  trialEnd: null,
  planName: "basic",
  planDisplayName: "Basic",
  planPriceMonthly: "30.00",
  planCurrency: "PLN",
  paymentMethod: {
    kind: "card_token",
    cardTail: "0016",
    cardBrand: "mastercard",
    tpayStatus: "active",
    isDefault: true,
  },
  pendingChange: null,
  graceUntil: null,
};

async function setup(): Promise<{
  fixture: ComponentFixture<SubscriptionDetailComponent>;
  httpMock: HttpTestingController;
}> {
  await TestBed.configureTestingModule({
    imports: [SubscriptionDetailComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      NoopAnimationsModule,
      provideRouter([]),
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(SubscriptionDetailComponent);
  return { fixture, httpMock: TestBed.inject(HttpTestingController) };
}

function flushDetail(
  httpMock: HttpTestingController,
  body: SubscriptionDetail,
): void {
  const req = httpMock.expectOne(`${environment.apiUrl}/billing/subscription`);
  expect(req.request.method).toBe("GET");
  req.flush(body);
}

describe("SubscriptionDetailComponent", () => {
  it("renderuje plan, cenę, okres i metodę płatności (AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, basicDetail);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Basic");
    expect(text).toContain("30,00 zł");
    expect(text).toContain("Aktywna");
    expect(text).toContain("MASTERCARD •••• 0016");
    expect(text).toContain("Plan");
    expect(text).toContain("Okres rozliczeniowy");
    httpMock.verify();
  });

  it("pokazuje przycisk „Anuluj subskrypcję” dla aktywnej subskrypcji płatnej (AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, basicDetail);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Anuluj subskrypcję");
    expect(text).not.toContain("Reaktywuj subskrypcję");
  });

  it("dla Freemium pokazuje „Uaktualnij plan” bez anulowania (AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, {
      ...basicDetail,
      planName: "freemium",
      planDisplayName: "Freemium",
      planPriceMonthly: "0.00",
      paymentMethod: null,
      nextChargeAt: null,
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Uaktualnij plan");
    expect(text).not.toContain("Anuluj subskrypcję");
    expect(text).toContain("Brak zapisanej metody");
  });

  it("anulowana subskrypcja: banner „aktywna do” i przycisk „Reaktywuj” (AC4/AC5)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, {
      ...basicDetail,
      cancelAtPeriodEnd: true,
      nextChargeAt: null,
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("anulowana — aktywna do");
    expect(text).toContain("Reaktywuj subskrypcję");
    expect(text).not.toContain("Anuluj subskrypcję");
  });

  it("zaplanowany downgrade (7.5): banner z planem docelowym (AC3)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, {
      ...basicDetail,
      planName: "premium",
      planDisplayName: "Premium",
      cancelAtPeriodEnd: true,
      nextChargeAt: null,
      pendingChange: {
        id: "ch-1",
        fromPlan: "premium",
        toPlan: "basic",
        changeType: "downgrade",
        status: "pending",
        requestedAt: "2026-09-10T00:00:00Z",
        effectiveAt: "2026-09-30T00:00:00Z",
        prorationDetails: {},
      },
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Zaplanowana zmiana planu");
    expect(text).toContain("basic");
  });

  it("wynik dialogu anulowania aktualizuje detail i pokazuje komunikat (AC4)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, basicDetail);
    fixture.detectChanges();

    const cancelled = {
      ...basicDetail,
      cancelAtPeriodEnd: true,
      nextChargeAt: null,
    };
    const dialog = TestBed.inject(MatDialog);
    vi.spyOn(dialog, "open").mockReturnValue({
      afterClosed: () => of(cancelled),
    } as never);

    fixture.componentInstance.openCancelDialog();
    fixture.detectChanges();

    expect(fixture.componentInstance.detail()).toEqual(cancelled);
    expect(fixture.componentInstance.actionInfo()).toContain("aktywna do");
  });

  it("reaktywacja woła POST /subscription/reactivate i aktualizuje stan (AC5)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    flushDetail(httpMock, {
      ...basicDetail,
      cancelAtPeriodEnd: true,
      nextChargeAt: null,
    });
    fixture.detectChanges();

    fixture.componentInstance.reactivate();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription/reactivate`,
    );
    expect(req.request.method).toBe("POST");
    req.flush(basicDetail);
    fixture.detectChanges();

    expect(fixture.componentInstance.detail()?.cancelAtPeriodEnd).toBe(false);
    expect(fixture.componentInstance.actionInfo()).toContain("jest aktywna");
  });

  it("błąd pobrania pokazuje komunikat z awarią (load error)", async () => {
    const { fixture, httpMock } = await setup();
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/subscription`)
      .flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nie udało się pobrać danych subskrypcji");
  });
});
