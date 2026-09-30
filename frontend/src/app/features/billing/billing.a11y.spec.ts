import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { vi } from "vitest";

import { environment } from "../../../environments/environment";
import {
  blockingViolations,
  formatViolations,
  runAxe,
} from "../../shared/utils/axe-setup";
import { SubscriptionDetail } from "./billing.service";
import { CancelConfirmDialogComponent } from "./subscription-manage/cancel-confirm-dialog/cancel-confirm-dialog.component";
import { SubscriptionDetailComponent } from "./subscription-manage/subscription-detail/subscription-detail.component";
import { TransactionListComponent } from "./transaction-list/transaction-list.component";

const API = environment.apiUrl;

const detail: SubscriptionDetail = {
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

/** Story 7.7, AC6 — portal billingowy bez naruszeń WCAG 2.1 AA. */
describe("Portal billingowy — dostępność (WCAG 2.1 AA)", () => {
  // axe.run() w jsdom jest CPU-żerny — podwyższony limit per-test (wzorzec 6.15).
  const AXE_TEST_TIMEOUT = 60_000;
  const itAxe = (name: string, fn: () => Promise<void>) =>
    it(name, fn, AXE_TEST_TIMEOUT);

  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
      ],
    });
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  async function expectNoViolations(element: Element): Promise<void> {
    const violations = blockingViolations(await runAxe(element));
    expect(formatViolations(violations)).toBe(
      "Brak naruszeń dostępności (WCAG 2.1 AA).",
    );
  }

  itAxe("szczegóły subskrypcji nie mają naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(SubscriptionDetailComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/billing/subscription`)
      .flush(detail);
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("dialog anulowania nie ma naruszeń krytycznych", async () => {
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [CancelConfirmDialogComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        { provide: MAT_DIALOG_DATA, useValue: detail },
        { provide: MatDialogRef, useValue: { close: vi.fn() } },
      ],
    }).compileComponents();
    httpTesting = TestBed.inject(HttpTestingController);

    const fixture = TestBed.createComponent(CancelConfirmDialogComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/billing/plans`)
      .flush({
        plans: [],
        currentPlan: "basic",
        termsUrl: "https://test-gen.pl/regulamin/",
        privacyPolicyUrl: "https://test-gen.pl/polityka/",
      });
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });

  itAxe("historia transakcji nie ma naruszeń krytycznych", async () => {
    const fixture = TestBed.createComponent(TransactionListComponent);
    fixture.detectChanges();
    httpTesting
      .expectOne((r) => r.url === `${API}/billing/transactions`)
      .flush({
        items: [
          {
            id: "txn-1",
            createdAt: "2026-09-10T14:32:00Z",
            amount: "50.00",
            currency: "PLN",
            status: "paid",
            paidAmount: "50.00",
            method: "card",
            transactionId: "ta_bKvkJX9Knk",
            orderId: "ord-1",
            invoiceId: "inv-1",
            invoiceNumber: "FV/2026/09/0003",
            testMode: false,
          },
        ],
        total: 1,
        page: 1,
        size: 20,
      });
    fixture.detectChanges();

    await expectNoViolations(fixture.nativeElement);
  });
});
