import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import {
  MAT_DIALOG_DATA,
  MatDialogRef,
} from "@angular/material/dialog";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { vi } from "vitest";

import { environment } from "../../../../../environments/environment";
import { Plan, Proration } from "../../billing.service";
import {
  PlanChangeConfirmComponent,
  PlanChangeConfirmData,
} from "./plan-change-confirm.component";

const basic: Plan = {
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
};

const premium: Plan = {
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
};

const upgradeProration: Proration = {
  amount: "10.00",
  periodDays: 30,
  remainingDays: 15,
  currentPlan: "basic",
  newPlan: "premium",
  currentPrice: "30.00",
  newPrice: "50.00",
  fullPrice: "50.00",
  changeType: "upgrade",
  currency: "PLN",
  nextChargeAt: "2026-09-18T12:00:00Z",
};

async function setup(data: PlanChangeConfirmData): Promise<{
  fixture: ComponentFixture<PlanChangeConfirmComponent>;
  httpMock: HttpTestingController;
  dialogRef: { close: ReturnType<typeof vi.fn> };
}> {
  const dialogRef = { close: vi.fn() };
  await TestBed.configureTestingModule({
    imports: [PlanChangeConfirmComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      NoopAnimationsModule,
      { provide: MAT_DIALOG_DATA, useValue: data },
      { provide: MatDialogRef, useValue: dialogRef },
    ],
  }).compileComponents();

  const fixture = TestBed.createComponent(PlanChangeConfirmComponent);
  return { fixture, httpMock: TestBed.inject(HttpTestingController), dialogRef };
}

function flushProration(
  httpMock: HttpTestingController,
  plan: string,
  body: Proration,
): void {
  const req = httpMock.expectOne(
    `${environment.apiUrl}/billing/subscription/proration?plan=${plan}`,
  );
  expect(req.request.method).toBe("GET");
  req.flush(body);
}

describe("PlanChangeConfirmComponent", () => {
  it("pobiera podgląd proration i pokazuje kwotę (AC5)", async () => {
    const { fixture, httpMock } = await setup({
      targetPlan: premium,
      currentPlan: basic,
    });
    fixture.detectChanges();
    flushProration(httpMock, "premium", upgradeProration);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("10.00 PLN");
    expect(text).toContain("15 z 30 dni");
    expect(text).toContain("natychmiast po opłaceniu");
    expect(text).toContain("50.00 PLN / mies.");
    httpMock.verify();
  });

  it("przy downgrade pokazuje ostrzeżenie, datę i utracone funkcje (AC7)", async () => {
    const { fixture, httpMock } = await setup({
      targetPlan: basic,
      currentPlan: premium,
    });
    fixture.detectChanges();
    flushProration(httpMock, "basic", {
      ...upgradeProration,
      amount: "0.00",
      changeType: "downgrade",
      currentPlan: "premium",
      newPlan: "basic",
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("na koniec bieżącego okresu");
    expect(text).toContain("2026-09-18");
    expect(text).toContain("Po zmianie utracisz:");
    expect(text).toContain("Mniej analiz miesięcznie");
    expect(text).toContain("Mniejszy storage");
    expect(text).toContain("Brak priorytetowego wsparcia");
    expect(text).toContain("możesz zrezygnować");
  });

  it("„Potwierdź” woła POST /subscription/change i zamyka dialog z wynikiem (AC1)", async () => {
    const { fixture, httpMock, dialogRef } = await setup({
      targetPlan: premium,
      currentPlan: basic,
    });
    fixture.detectChanges();
    flushProration(httpMock, "premium", upgradeProration);
    fixture.detectChanges();

    fixture.componentInstance.confirm();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription/change`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({ plan: "premium" });
    const result = {
      change: { id: "ch-1" },
      changeType: "upgrade",
      amount: "10.00",
      currency: "PLN",
      paymentRequired: true,
      paymentUrl: "https://secure.tpay.com/panel/x",
      orderId: "ord-1",
    };
    req.flush(result);

    expect(dialogRef.close).toHaveBeenCalledWith(
      expect.objectContaining({ paymentUrl: "https://secure.tpay.com/panel/x" }),
    );
  });

  it("pokazuje detail błędu z API i nie zamyka dialogu (409 dunning)", async () => {
    const { fixture, httpMock, dialogRef } = await setup({
      targetPlan: basic,
      currentPlan: premium,
    });
    fixture.detectChanges();
    flushProration(httpMock, "basic", {
      ...upgradeProration,
      amount: "0.00",
      changeType: "downgrade",
    });
    fixture.detectChanges();

    fixture.componentInstance.confirm();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription/change`,
    );
    req.flush(
      { detail: "Subskrypcja w trakcie windykacji" },
      { status: 409, statusText: "Conflict" },
    );
    fixture.detectChanges();

    expect(dialogRef.close).not.toHaveBeenCalled();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Subskrypcja w trakcie windykacji");
    expect(fixture.componentInstance.submitting()).toBe(false);
  });

  it("„Anuluj” zamyka dialog bez wyniku", async () => {
    const { fixture, httpMock, dialogRef } = await setup({
      targetPlan: premium,
      currentPlan: basic,
    });
    fixture.detectChanges();
    flushProration(httpMock, "premium", upgradeProration);

    fixture.componentInstance.cancel();
    expect(dialogRef.close).toHaveBeenCalledWith();
  });
});
