import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { environment } from "../../../../../environments/environment";
import { TransactionStatusResponse } from "../../billing.service";
import { ModuleLocksService } from "../../../../core/services/module-locks.service";
import { CheckoutSuccessComponent } from "./checkout-success.component";

const ORDER_ID = "ord-123";

function statusResponse(status: string): TransactionStatusResponse {
  return {
    orderId: ORDER_ID,
    status: status as TransactionStatusResponse["status"],
    plan: "basic",
    amount: "30.00",
    currency: "PLN",
    testMode: true,
  };
}

describe("CheckoutSuccessComponent", () => {
  let fixture: ComponentFixture<CheckoutSuccessComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    sessionStorage.clear();
    // Projekt zoneless (Angular 21) — bez fakeAsync/zone-testing; timery
    // parchujemy przez vi.useFakeTimers, zapytania przez HttpTestingController.
    vi.useFakeTimers();
    await TestBed.configureTestingModule({
      imports: [CheckoutSuccessComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
        // Story 7.13 — refresh blokad po paid nie jest przedmiotem tego specu.
        { provide: ModuleLocksService, useValue: { refresh: () => undefined } },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function create(): void {
    fixture = TestBed.createComponent(CheckoutSuccessComponent);
  }

  function pollCycle(status: string): void {
    vi.advanceTimersByTime(2000);
    const req = httpMock.expectOne(
      `${environment.apiUrl}/billing/transactions/${ORDER_ID}`,
    );
    expect(req.request.method).toBe("GET");
    req.flush(statusResponse(status));
  }

  it("bez order_id w sessionStorage pokazuje komunikat i nie odpytuje API", () => {
    create();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nie znaleziono informacji o rozpoczętej płatności");
    httpMock.verify();
  });

  it("polling: pending → paid pokazuje aktywny plan i kwotę (AC2)", () => {
    sessionStorage.setItem("tg_checkout_order_id", ORDER_ID);
    create();
    fixture.detectChanges();

    pollCycle("pending");
    fixture.detectChanges();
    expect(fixture.componentInstance.view()).toBe("checking");

    pollCycle("paid");
    fixture.detectChanges();

    expect(fixture.componentInstance.view()).toBe("paid");
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Plan Basic — aktywny");
    expect(text).toContain("30.00 PLN");
    expect(text).toContain("Faktura VAT");

    // po paid polling się zatrzymuje (klucz sessionStorage wyczyszczony)
    vi.advanceTimersByTime(10000);
    httpMock.verify();
    expect(sessionStorage.getItem("tg_checkout_order_id")).toBeNull();
    fixture.componentInstance.ngOnDestroy();
  });

  it("po 60 s bez potwierdzenia pokazuje stan przejściowy (AC2/AC6)", () => {
    sessionStorage.setItem("tg_checkout_order_id", ORDER_ID);
    create();
    fixture.detectChanges();

    for (let i = 0; i < 30; i++) {
      pollCycle("pending");
    }
    fixture.detectChanges();

    expect(fixture.componentInstance.view()).toBe("timeout");
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("potwierdzenie jeszcze nie dotarło");
    fixture.componentInstance.ngOnDestroy();
  });
});
