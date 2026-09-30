import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { vi } from "vitest";

import { environment } from "../../../../../environments/environment";
import { Plan, PlanChange, SubscriptionDetail } from "../../billing.service";
import { CancelConfirmDialogComponent } from "./cancel-confirm-dialog.component";

const premiumDetail: SubscriptionDetail = {
  id: "sub-1",
  tenantId: "t-1",
  planId: "plan-premium",
  status: "active",
  currentPeriodStart: "2026-09-01T00:00:00Z",
  currentPeriodEnd: "2026-09-30T00:00:00Z",
  nextChargeAt: "2026-09-30T00:00:00Z",
  cancelAtPeriodEnd: false,
  trialEnd: null,
  planName: "premium",
  planDisplayName: "Premium",
  planPriceMonthly: "50.00",
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

const plansBody: { plans: Plan[] } = {
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
        storageBytes: 512 * 1024 * 1024,
        filesPerAnalysis: 5,
        rateLimitPerMin: 100,
        prioritySupport: false,
      },
      isActive: true,
      sortOrder: 0,
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
};

async function setup(data: SubscriptionDetail): Promise<{
  fixture: ComponentFixture<CancelConfirmDialogComponent>;
  httpMock: HttpTestingController;
  dialogRef: { close: ReturnType<typeof vi.fn> };
}> {
  const dialogRef = { close: vi.fn() };
  await TestBed.configureTestingModule({
    imports: [CancelConfirmDialogComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      NoopAnimationsModule,
      { provide: MAT_DIALOG_DATA, useValue: data },
      { provide: MatDialogRef, useValue: dialogRef },
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(CancelConfirmDialogComponent);
  return {
    fixture,
    httpMock: TestBed.inject(HttpTestingController),
    dialogRef,
  };
}

function flushPlans(httpMock: HttpTestingController): void {
  const req = httpMock.expectOne(`${environment.apiUrl}/billing/plans`);
  expect(req.request.method).toBe("GET");
  req.flush({
    ...plansBody,
    currentPlan: "premium",
    termsUrl: "https://test-gen.pl/regulamin/",
    privacyPolicyUrl: "https://test-gen.pl/polityka/",
  });
}

describe("CancelConfirmDialogComponent", () => {
  it("pokazuje datę wygaśnięcia, powrót do Freemium i utracone funkcje (AC4)", async () => {
    const { fixture, httpMock } = await setup(premiumDetail);
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("30.09.2026");
    expect(text).toContain("freemium");
    expect(text).toContain("Co tracisz po zmianie planu");
    expect(text).toContain("Mniej analiz miesięcznie");
    expect(text).toContain("Brak priorytetowego wsparcia");
    httpMock.verify();
  });

  it("przy zaplanowanym downgrade (7.5) pokazuje plan niższy zamiast Freemium (AC4)", async () => {
    const pending: PlanChange = {
      id: "ch-1",
      fromPlan: "premium",
      toPlan: "basic",
      changeType: "downgrade",
      status: "pending",
      requestedAt: "2026-09-10T00:00:00Z",
      effectiveAt: "2026-09-30T00:00:00Z",
      prorationDetails: {},
    };
    const { fixture, httpMock } = await setup({
      ...premiumDetail,
      pendingChange: pending,
    });
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    expect(fixture.componentInstance.effectivePlan()).toBe("basic");
  });

  it("„Potwierdź” woła POST /subscription/cancel i zamyka dialog z detail (AC4)", async () => {
    const { fixture, httpMock, dialogRef } = await setup(premiumDetail);
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    fixture.componentInstance.confirm();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription/cancel`,
    );
    expect(req.request.method).toBe("POST");
    const cancelled = {
      ...premiumDetail,
      cancelAtPeriodEnd: true,
      nextChargeAt: null,
    };
    req.flush(cancelled);

    expect(dialogRef.close).toHaveBeenCalledWith(cancelled);
  });

  it("pokazuje detail błędu z API i nie zamyka dialogu (409)", async () => {
    const { fixture, httpMock, dialogRef } = await setup(premiumDetail);
    fixture.detectChanges();
    flushPlans(httpMock);
    fixture.detectChanges();

    fixture.componentInstance.confirm();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription/cancel`,
    );
    req.flush(
      { detail: "Subskrypcja jest już anulowana — aktywna do końca okresu" },
      { status: 409, statusText: "Conflict" },
    );
    fixture.detectChanges();

    expect(dialogRef.close).not.toHaveBeenCalled();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Subskrypcja jest już anulowana");
    expect(fixture.componentInstance.submitting()).toBe(false);
  });

  it("„Wróć” zamyka dialog bez wyniku", async () => {
    const { fixture, httpMock, dialogRef } = await setup(premiumDetail);
    fixture.detectChanges();
    flushPlans(httpMock);

    fixture.componentInstance.cancel();
    expect(dialogRef.close).toHaveBeenCalledWith();
  });

  it("bez macierzy planów (błąd GET /plans) dialog nadal działa", async () => {
    const { fixture, httpMock } = await setup(premiumDetail);
    fixture.detectChanges();
    httpMock
      .expectOne(`${environment.apiUrl}/billing/plans`)
      .flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    expect(fixture.componentInstance.lostFeatures()).toEqual([]);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("30.09.2026");
  });
});
