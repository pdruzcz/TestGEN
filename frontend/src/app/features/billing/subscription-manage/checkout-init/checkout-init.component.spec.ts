import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import {
  ActivatedRoute,
  convertToParamMap,
  provideRouter,
} from "@angular/router";

import { FlutterBridgeService } from "../../../../shared/services/flutter-bridge.service";
import { environment } from "../../../../../environments/environment";
import { CheckoutResponse } from "../../billing.service";
import { CheckoutInitComponent } from "./checkout-init.component";

const mockCheckout: CheckoutResponse = {
  orderId: "ord-123",
  transactionId: "ta_bKvkJX9Knk9Ol4od",
  transactionPaymentUrl: "https://sandbox.tpay.com/pay/ta_bKvkJX9Knk9Ol4od",
  plan: "basic",
  amount: "30.00",
  currency: "PLN",
};

class FakeFlutterBridge {
  isFlutterEnvironment = vi.fn(() => true);
  openExternal = vi.fn();
}

describe("CheckoutInitComponent", () => {
  let fixture: ComponentFixture<CheckoutInitComponent>;
  let httpMock: HttpTestingController;
  let flutter: FakeFlutterBridge;

  beforeEach(async () => {
    flutter = new FakeFlutterBridge();
    sessionStorage.clear();
  });

  async function createWithPlan(plan: string): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [CheckoutInitComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
        { provide: FlutterBridgeService, useValue: flutter },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: convertToParamMap({ plan }) },
          },
        },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(CheckoutInitComponent);
    fixture.detectChanges();
  }

  it("POST /billing/checkout i URL tpay w zewnętrznej przeglądarce (AC1/AC2 Flutter)", async () => {
    await createWithPlan("basic");

    const req = httpMock.expectOne(`${environment.apiUrl}/billing/checkout`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({ plan: "basic" });
    req.flush(mockCheckout);
    fixture.detectChanges();

    // order_id w sessionStorage przed przekierowaniem (polling stron powrotu — AC2)
    expect(sessionStorage.getItem("tg_checkout_order_id")).toBe("ord-123");
    // WebView: URL tpay w zewnętrznej przeglądarce (3DS/BLIK → aplikacja banku)
    expect(flutter.openExternal).toHaveBeenCalledWith(
      mockCheckout.transactionPaymentUrl,
    );
    httpMock.verify();
  });

  it("odrzuca plan inny niż basic/premium bez wywołania API", async () => {
    await createWithPlan("freemium");

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Nieprawidłowy plan");
    httpMock.expectNone(`${environment.apiUrl}/billing/checkout`);
    httpMock.verify();
  });

  it("mapuje 409 na komunikat o aktywnym planie płatnym (AC1)", async () => {
    await createWithPlan("premium");

    const req = httpMock.expectOne(`${environment.apiUrl}/billing/checkout`);
    req.flush("conflict", { status: 409, statusText: "Conflict" });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain("Masz już aktywny plan płatny");
    expect(fixture.componentInstance.loading()).toBe(false);
    httpMock.verify();
  });
});
