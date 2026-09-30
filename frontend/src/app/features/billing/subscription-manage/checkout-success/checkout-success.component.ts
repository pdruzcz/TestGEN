import { Component, OnDestroy, inject, signal } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink } from "@angular/router";

import { BillingService } from "../../billing.service";
import { CHECKOUT_ORDER_KEY } from "../checkout-init/checkout-init.component";
import { ModuleLocksService } from "../../../../core/services/module-locks.service";

/** Polling statusu transakcji (AC2): co 2 s, maks. 60 s. */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 30;

type ViewState = "checking" | "paid" | "timeout";

/**
 * Strona powrotu tpay po udanej płatności (Story 7.4, AC2/AC6).
 *
 * Kolejność powrotu płatnika i webhooka nie jest gwarantowana — strona
 * odpyta backend o status transakcji (polling), a backend w razie potrzeby
 * wykona jednorazowy fallback reconciliation u tpay (AC7).
 */
@Component({
  selector: "app-checkout-success",
  imports: [MatCardModule, MatButton, MatProgressSpinnerModule, RouterLink],
  templateUrl: "./checkout-success.component.html",
  styleUrl: "./checkout-success.component.scss",
  providers: [BillingService],
})
export class CheckoutSuccessComponent implements OnDestroy {
  private readonly billing = inject(BillingService);

  /** Story 7.13 — reaktywny unlock: po paid blokady modułów znikają bez reloadu. */
  private readonly moduleLocks = inject(ModuleLocksService);

  readonly view = signal<ViewState>("checking");
  readonly planLabel = signal("");
  readonly amountLabel = signal("");
  readonly noOrder = signal(false);

  private attempts = 0;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    const orderId = sessionStorage.getItem(CHECKOUT_ORDER_KEY);
    if (!orderId) {
      this.noOrder.set(true);
      return;
    }
    this.poll(orderId);
  }

  ngOnDestroy(): void {
    this.stopTimer();
  }

  private poll(orderId: string): void {
    this.timer = setInterval(() => {
      this.attempts++;
      this.billing.getTransactionStatus(orderId).subscribe({
        next: (status) => {
          if (status.status === "paid") {
            // Klucz czyścimy dopiero po paid — refresh strony w trakcie
            // pollingu nie gubi order_id.
            sessionStorage.removeItem(CHECKOUT_ORDER_KEY);
            this.planLabel.set(
              status.plan
                ? `Plan ${status.plan[0].toUpperCase()}${status.plan.slice(1)}`
                : "Subskrypcja",
            );
            this.amountLabel.set(
              `Opłacono: ${status.amount} ${status.currency} (rozliczenie miesięczne)`,
            );
            this.view.set("paid");
            this.moduleLocks.refresh();
            this.stopTimer();
          } else if (this.attempts >= POLL_MAX_ATTEMPTS) {
            this.view.set("timeout");
            this.stopTimer();
          }
        },
        error: () => {
          if (this.attempts >= POLL_MAX_ATTEMPTS) {
            this.view.set("timeout");
            this.stopTimer();
          }
        },
      });
    }, POLL_INTERVAL_MS);
  }

  private stopTimer(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
