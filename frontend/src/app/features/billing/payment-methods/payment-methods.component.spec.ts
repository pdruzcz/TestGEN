import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { FlutterBridgeService } from "../../../shared/services/flutter-bridge.service";
import { environment } from "../../../../environments/environment";
import { PaymentMethod } from "../billing.service";
import {
  PAYMENT_METHOD_REGISTRATION_KEY,
  PaymentMethodsComponent,
} from "./payment-methods.component";

const mockMethods: PaymentMethod[] = [
  {
    id: "tok-1",
    kind: "card_token",
    cardTail: "4242",
    cardBrand: "visa",
    tpayStatus: "active",
    isDefault: true,
    createdAt: "2026-09-01T10:00:00Z",
  },
  {
    id: "tok-2",
    kind: "blik_alias_payid",
    cardTail: null,
    cardBrand: null,
    tpayStatus: "pending",
    isDefault: false,
    createdAt: "2026-09-02T12:00:00Z",
  },
  {
    id: "tok-3",
    kind: "card_token",
    cardTail: "0016",
    cardBrand: "mastercard",
    tpayStatus: "deleted",
    isDefault: false,
    createdAt: "2026-08-01T10:00:00Z",
  },
];

class FakeFlutterBridge {
  isFlutterEnvironment = vi.fn(() => false);
  openExternal = vi.fn();
}

describe("PaymentMethodsComponent (Story 7.2, AC2/AC3)", () => {
  let fixture: ComponentFixture<PaymentMethodsComponent>;
  let httpMock: HttpTestingController;
  let flutter: FakeFlutterBridge;

  beforeEach(async () => {
    flutter = new FakeFlutterBridge();
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [PaymentMethodsComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
        { provide: FlutterBridgeService, useValue: flutter },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PaymentMethodsComponent);
    fixture.detectChanges();
  });

  function flushListAndSubscription(status = "active"): void {
    const subReq = httpMock.expectOne(
      `${environment.apiUrl}/billing/subscription`,
    );
    subReq.flush({
      id: "sub-1",
      tenantId: "t-1",
      planId: "p-1",
      status,
      currentPeriodStart: "2026-09-01T00:00:00Z",
      currentPeriodEnd: "2026-10-01T00:00:00Z",
      nextChargeAt: "2026-10-01T00:00:00Z",
      cancelAtPeriodEnd: false,
      trialEnd: null,
    });
    const listReq = httpMock.expectOne(
      `${environment.apiUrl}/billing/payment-methods`,
    );
    listReq.flush(mockMethods);
    fixture.detectChanges();
  }

  it("GET /billing/payment-methods — lista bez usuniętych, chipy statusów (AC3)", () => {
    flushListAndSubscription();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("VISA •••• 4242");
    expect(text).toContain("Domyślna");
    expect(text).toContain("Aktywna");
    expect(text).toContain("Płatności Powtarzalne");
    expect(text).toContain("W trakcie rejestracji");
    // soft-deleted metoda niewidoczna na liście
    expect(text).not.toContain("0016");
    httpMock.verify();
  });

  it("banner past_due przy zaległej subskrypcji (AC6)", () => {
    flushListAndSubscription("past_due");

    const banner = fixture.nativeElement.querySelector(
      ".banner-warning",
    ) as HTMLElement | null;
    expect(banner).not.toBeNull();
    expect(banner!.textContent).toContain("Płatność za subskrypcję");
  });

  it("POST /billing/payment-methods — zapis tokenId i redirect (AC2)", () => {
    flushListAndSubscription();
    const redirectSpy = vi.spyOn(fixture.componentInstance, "redirectTo");

    fixture.componentInstance.addCard();
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/payment-methods`,
    );
    expect(req.request.method).toBe("POST");
    req.flush({ tokenId: "tok-new", registrationUrl: "https://tpay/reg" });
    fixture.detectChanges();

    expect(sessionStorage.getItem(PAYMENT_METHOD_REGISTRATION_KEY)).toBe(
      "tok-new",
    );
    expect(redirectSpy).toHaveBeenCalledWith("https://tpay/reg");
    httpMock.verify();
  });

  it("DELETE 409 — komunikat o ostatniej metodzie subskrypcji (AC3)", () => {
    flushListAndSubscription();

    fixture.componentInstance.remove(mockMethods[0]);
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/payment-methods/tok-1`,
    );
    expect(req.request.method).toBe("DELETE");
    req.flush("conflict", { status: 409, statusText: "Conflict" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("jedyna aktywna metoda płatności");
    expect(fixture.componentInstance.methods().length).toBe(2);
    httpMock.verify();
  });

  it("DELETE 200 — metoda znika z listy (AC3)", () => {
    flushListAndSubscription();

    fixture.componentInstance.remove(mockMethods[0]);
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/payment-methods/tok-1`,
    );
    req.flush({ ...mockMethods[0], tpayStatus: "deleted" });
    fixture.detectChanges();

    expect(fixture.componentInstance.methods().length).toBe(1);
    httpMock.verify();
  });
});
