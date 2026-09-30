import { Component, inject, signal } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { ActivatedRoute, RouterLink } from "@angular/router";

import { FlutterBridgeService } from "../../../../shared/services/flutter-bridge.service";
import { BillingService, PaidPlan } from "../../billing.service";

/** Klucz sessionStorage — order_id potrzebny stronom powrotu do pollingu statusu. */
export const CHECKOUT_ORDER_KEY = "tg_checkout_order_id";

const PAID_PLANS: PaidPlan[] = ["basic", "premium"];

/**
 * Inicjacja checkoutu tpay (Story 7.4, AC2) — strona docelowa CTA z /billing/plans.
 *
 * Polling kolejności powrotu płatnika i webhooka nie jest gwarantowany —
 * dlatego order_id ląduje w sessionStorage przed przekierowaniem, a strony
 * powrotu odpytują backend o status transakcji.
 *
 * Flutter WebView: 3DS/BLIK wymagają przełączeń na aplikację banku, więc
 * URL tpay otwierany jest w zewnętrznej przeglądarce (deep link powrotu
 * obsługuje shell mobilny); w przeglądarce — zwykły redirect.
 */
@Component({
  selector: "app-checkout-init",
  imports: [MatCardModule, MatButton, MatProgressSpinnerModule, RouterLink],
  templateUrl: "./checkout-init.component.html",
  styleUrl: "./checkout-init.component.scss",
  providers: [BillingService],
})
export class CheckoutInitComponent {
  private readonly billing = inject(BillingService);
  private readonly route = inject(ActivatedRoute);
  private readonly flutter = inject(FlutterBridgeService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  constructor() {
    const planParam = this.route.snapshot.queryParamMap.get("plan");
    if (!PAID_PLANS.includes(planParam as PaidPlan)) {
      this.error.set(
        "Nieprawidłowy plan — wybierz plan płatny na stronie planów.",
      );
      this.loading.set(false);
      return;
    }
    const plan = planParam as PaidPlan;

    this.billing.createCheckout(plan).subscribe({
      next: (checkout) => {
        sessionStorage.setItem(CHECKOUT_ORDER_KEY, checkout.orderId);
        this.openPaymentUrl(checkout.transactionPaymentUrl);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err?.status));
        this.loading.set(false);
      },
    });
  }

  /** AC2/Flutter: zewnętrzna przeglądarka w WebView, redirect w web app. */
  private openPaymentUrl(url: string): void {
    if (this.flutter.isFlutterEnvironment()) {
      // Deep link powrotu (testgen://…) obsługuje shell mobilny (FlutterBridgeService).
      this.flutter.openExternal(url);
      this.loading.set(false);
      return;
    }
    window.location.href = url;
  }

  private errorMessage(status: number | undefined): string {
    if (status === 403) {
      return "Tylko administrator konta (Owner) może opłacić subskrypcję.";
    }
    if (status === 409) {
      return "Masz już aktywny plan płatny. Zmianę planu wykonasz w panelu subskrypcji.";
    }
    return "Nie udało się rozpocząć płatności. Spróbuj ponownie za chwilę.";
  }
}
