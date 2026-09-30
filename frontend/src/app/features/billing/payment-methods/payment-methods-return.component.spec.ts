import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../environments/environment";
import { PaymentMethod } from "../billing.service";
import { PAYMENT_METHOD_REGISTRATION_KEY } from "./payment-methods.component";
import { PaymentMethodsReturnComponent } from "./payment-methods-return.component";

const pendingMethod: PaymentMethod = {
  id: "tok-reg",
  kind: "card_token",
  cardTail: null,
  cardBrand: null,
  tpayStatus: "pending",
  isDefault: false,
  createdAt: "2026-09-02T10:00:00Z",
};

describe("PaymentMethodsReturnComponent (Story 7.2, AC2)", () => {
  let fixture: ComponentFixture<PaymentMethodsReturnComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    sessionStorage.clear();
    vi.useFakeTimers();
    await TestBed.configureTestingModule({
      imports: [PaymentMethodsReturnComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PaymentMethodsReturnComponent);
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function flushMethods(method: PaymentMethod | null): void {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/payment-methods`,
    );
    req.flush(method ? [method] : []);
    fixture.detectChanges();
  }

  it("bez tokenId w sessionStorage — stan missing (brak rejestracji)", () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nie znaleziono informacji o rejestracji");
    httpMock.verify();
  });

  it("polling do potwierdzenia — pending → active = confirmed (AC2)", async () => {
    sessionStorage.setItem(PAYMENT_METHOD_REGISTRATION_KEY, "tok-reg");
    fixture = TestBed.createComponent(PaymentMethodsReturnComponent);
    fixture.detectChanges();

    // 1. próba (timer(0) — tick pod fake timers): wciąż pending
    await vi.advanceTimersByTimeAsync(0);
    flushMethods(pendingMethod);
    expect(fixture.componentInstance.state()).toBe("polling");

    // 2. próba (po 3 s): aktywna → confirmed + czyszczenie sessionStorage
    await vi.advanceTimersByTimeAsync(3000);
    flushMethods({ ...pendingMethod, tpayStatus: "active" });

    expect(fixture.componentInstance.state()).toBe("confirmed");
    expect(sessionStorage.getItem(PAYMENT_METHOD_REGISTRATION_KEY)).toBeNull();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Karta została zapisana");
    httpMock.verify();
  });
});
